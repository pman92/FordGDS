# Copyright (c) 2025 MR MODULE PTY LTD
# Licensed under the MIT License

import serial
import threading
import time
import tkinter as tk

eeprom_mon_port = 'COM14'

CMD_READ_ALL = 0x11
CMD_GET_ACCESSED = 0x30
CMD_GET_MODIFIED = 0x31
CMD_CLEAR_FLAGS = 0xA1
CMD_RESET_ALL = 0xA0
CMD_BOOT_FLAG = 0x0A

class EepromMonitor:
    def __init__(self, port, baud=38400, poll_interval=0.5):
        self.on_accessed = None
        self.on_modified = None
        self.accessed_once = [False] * 256
        self.modified_once = [False] * 256
        self.port = port
        self.baud = baud
        self.poll_interval = poll_interval

        self.ser = serial.Serial(port, baudrate=baud, timeout=1)
        self.ser.reset_input_buffer()  # Clear any incoming serial data
        self.eeprom = [0x00] * 256
        self.accessed = [False] * 256
        self.modified = [False] * 256

        self.running = True
        self.gui_thread = threading.Thread(target=self._start_gui)
        self.poll_thread = threading.Thread(target=self._poll_loop)

        self._read_eeprom()  # Ensure full initialization

    def start(self):
        self.gui_thread.start()
        self.poll_thread.start()

    def stop(self):
        self.running = False
        if self.ser.is_open:
            self.ser.close()
        try:
            if self.root:
                self.root.after(0, self.root.quit)  # Schedule quit on GUI thread
        except AttributeError:
            pass

    def _poll_loop(self):
        while self.running:
            self._read_flags()
            self._read_eeprom()
            time.sleep(self.poll_interval)

    def _read_eeprom(self):
        for base_addr in range(0, 256, 32):
            packet = bytes([CMD_READ_ALL, 0x04, base_addr, (CMD_READ_ALL + 0x04 + base_addr) & 0xFF])
            self.ser.write(packet)
            response = self._read_response(36, CMD_READ_ALL)

            if response:
                reported_addr = response[2]
                if reported_addr == base_addr:
                    for i in range(32):
                        self.eeprom[base_addr + i] = response[3 + i]
            time.sleep(0.01)

    def _read_flags(self):
        for cmd, target in [(CMD_GET_ACCESSED, self.accessed), (CMD_GET_MODIFIED, self.modified)]:
            packet = bytes([cmd, 0x03, (cmd + 0x03) & 0xFF])
            self.ser.write(packet)
            response = self._read_response(35, cmd)
            if response:
                flags = response[2:34]
                for i in range(256):
                    byte_index = i // 8
                    bit_index = i % 8
                    new_state = bool(flags[byte_index] & (1 << bit_index))
                    if new_state and not target[i]:
                        if target is self.accessed and not self.accessed_once[i]:
                            self.accessed_once[i] = True
                            if self.on_accessed:
                                self.on_accessed(i, self.eeprom[i])
                        elif target is self.modified and not self.modified_once[i]:
                            self.modified_once[i] = True
                            if self.on_modified:
                                self.on_modified(i, self.eeprom[i])
                    target[i] = new_state
            time.sleep(0.01)

    def _read_response(self, expected_len, expected_cmd):
        buffer = bytearray()
        timeout = time.time() + 0.5
        while time.time() < timeout:
            if self.ser.in_waiting:
                buffer += self.ser.read(self.ser.in_waiting)
                while len(buffer) >= expected_len:
                    if buffer[0] == expected_cmd and buffer[1] == expected_len:
                        return buffer[:expected_len]
                    else:
                        buffer.pop(0)
            time.sleep(0.005)
        return None

    def _start_gui(self):
        self.root = tk.Tk()
        self.root.title("EEPROM Monitor")

        # Add column labels (01 to 0F)
        for col in range(16):
            label = tk.Label(self.root, text=f"{col:02X}", width=4, relief="flat", borderwidth=0, fg="gray")
            label.grid(row=0, column=col+1)

        # Add row labels (00 to F0)
        for row in range(16):
            label = tk.Label(self.root, text=f"{row*16:02X}", width=4, relief="flat", borderwidth=0, fg="gray")
            label.grid(row=row+1, column=0)

        self.cells = []
        for row in range(16):
            for col in range(16):
                idx = row * 16 + col
                label = tk.Label(self.root, text="00", width=4, relief="ridge", borderwidth=1)
                label.grid(row=row + 1, column=col + 1, padx=1, pady=1)
                label.bind("<Button-1>", lambda e, i=idx: self._edit_cell(i))
                self.cells.append(label)

        self._update_gui()

        # Add control buttons below the table
        eeprom_frame = tk.LabelFrame(self.root, text="Persistent EEPROM")
        eeprom_frame.grid(row=18, rowspan=2, column=0, columnspan=5, pady=(10, 0), padx=5, sticky="w")
        tk.Button(eeprom_frame, text="Save Data", command=self._save_data).grid(row=0, column=0, padx=5, pady=5)
        tk.Button(eeprom_frame, text="Load Data", command=self._load_data).grid(row=1, column=0, padx=5, pady=5)
        tk.Button(eeprom_frame, text="Save Flags", command=self._save_flags).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(eeprom_frame, text="Load Flags", command=self._load_flags).grid(row=1, column=1, padx=5, pady=5)

        # Legend label for colors
        legend_frame = tk.Frame(self.root)
        legend_frame.grid(row=18, column=4, columnspan=9, pady=(5, 0), sticky="n")

        tk.Label(legend_frame, text="", width=2, bg="#FFD966").pack(side="left", padx=(0, 2))
        tk.Label(legend_frame, text="= Accessed").pack(side="left", padx=(5, 15))
        tk.Label(legend_frame, text="", width=2, bg="red").pack(side="left", padx=(0, 2))
        tk.Label(legend_frame, text="= Modified").pack(side="left")

        # Attribution label
        info_label = tk.Label(self.root, text="" \
        "24C02 Serial EEPROM Emulator Utility\n" \
        "© 2025 Mr Module Pty Ltd\n" \
        "mrmodule.com.au", fg="gray")
        info_label.grid(row=19, column=4, columnspan=9, pady=(0, 0), sticky="n")

        # Save / load etc.
        utility_frame = tk.Frame(self.root)
        utility_frame.grid(row=18, rowspan=2, column=12, columnspan=5, pady=(10, 0), padx=5, sticky="e")
        tk.Button(utility_frame, text="Reset Data", command=self._reset_data).grid(row=0, column=0, padx=5, pady=5)
        tk.Button(utility_frame, text="Clear Flags", command=self._clear_flags).grid(row=1, column=0, padx=5, pady=5)
        tk.Button(utility_frame, text="Save .bin", command=self._export_bin).grid(row=0, column=2, padx=5, pady=5)
        tk.Button(utility_frame, text="Load .bin", command=self._import_bin).grid(row=1, column=2, padx=5, pady=5)


        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
    
    def _save_data(self):
        packet = bytes([0x40, 0x03, (0x40 + 0x03) & 0xFF])
        self.ser.write(packet)

    def _save_flags(self):
        packet = bytes([0x42, 0x03, (0x42 + 0x03) & 0xFF])
        self.ser.write(packet)

    def _load_data(self):
        packet = bytes([0x41, 0x03, (0x41 + 0x03) & 0xFF])
        self.ser.write(packet)

    def _load_flags(self):
        packet = bytes([0x43, 0x03, (0x43 + 0x03) & 0xFF])
        self.ser.write(packet)

    def _reset_data(self):
        packet = bytes([0xA0, 0x03, (0xA0 + 0x03) & 0xFF])
        self.ser.write(packet)

    def _clear_flags(self):
        packet = bytes([0xA1, 0x03, (0xA1 + 0x03) & 0xFF])
        self.ser.write(packet)

    def _export_bin(self):
        from tkinter import filedialog
        file_path = filedialog.asksaveasfilename(defaultextension=".bin", filetypes=[("Binary files", "*.bin")])
        if file_path:
            with open(file_path, 'wb') as f:
                f.write(bytes(self.eeprom))

    def _import_bin(self):
        from tkinter import filedialog, messagebox
        file_path = filedialog.askopenfilename(filetypes=[("Binary files", "*.bin")])
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                    if len(data) != 256:
                        messagebox.showerror("Import Error", "Binary file must be exactly 256 bytes.")
                        return
                    self.eeprom = list(data)
                    self._clear_flags()
                    for base_addr in range(0, 256, 32):
                        chunk = self.eeprom[base_addr:base_addr + 32]
                        packet = bytes([0x21, 0x24, base_addr] + chunk + [(0x21 + 0x24 + base_addr + sum(chunk)) & 0xFF])
                        self.ser.write(packet)
                        time.sleep(0.01)
                    self._update_gui()
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import file:{e}")

    def _on_close(self):
        self._save_data()
        self._save_flags()
        time.sleep(0.1)  # Give time for serial writes to complete
        self.stop()

    def _edit_cell(self, index):
        label = self.cells[index]
        label.grid_remove()

        entry = tk.Entry(self.root, width=4, justify="center")
        entry.insert(0, f"{self.eeprom[index]:02X}")
        entry.icursor(0)
        entry.config(fg="blue")

        user_started_typing = {'typed': False}
        entry.grid(row=(index // 16) + 1, column=(index % 16) + 1, padx=1, pady=1)
        entry.focus()

        def validate_hex_input(event=None):
            val = entry.get().upper()
            if len(val) == 2 and all(c in '0123456789ABCDEF' for c in val):
                self.eeprom[index] = int(val, 16)
                self.modified[index] = True
                self._send_byte_to_arduino(index)
                self._update_gui()
                entry.destroy()
                label.grid()
            elif len(val) > 2:
                entry.delete(2, tk.END)

        def advance_on_input(event):
            if not user_started_typing['typed']:
                user_started_typing['typed'] = True
                char = event.char.upper()
                if char in '0123456789ABCDEF':
                    entry.delete(0, tk.END)
                    entry.insert(0, char)
                    entry.icursor(1)
                entry.config(fg="black")
                return

            if event.keysym == 'Return':
                validate_hex_input()
            elif event.char.upper() in '0123456789ABCDEF':
                entry.delete(2, tk.END)
                if len(entry.get()) >= 2:
                    validate_hex_input()
                    next_index = (index + 1) % 256
                    self._edit_cell(next_index)

        entry.bind("<KeyRelease>", advance_on_input)
        entry.bind("<FocusOut>", lambda e: (validate_hex_input(), entry.destroy(), label.grid()))
        entry.bind("<Escape>", lambda e: (entry.destroy(), label.grid()))

        def validate_char(event):
            if event.keysym == 'Return':
                return True
            return event.char.upper() in '0123456789ABCDEF'

        entry.bind("<KeyPress>", lambda e: validate_char(e) or "break")

    def _send_byte_to_arduino(self, index):
        addr = index
        val = self.eeprom[index]
        packet = bytes([0x20, 0x05, addr, val, (0x20 + 0x05 + addr + val) & 0xFF])
        self.ser.write(packet)

    def _update_gui(self):
        for i in range(256):
            val = self.eeprom[i]
            label = self.cells[i]
            label.config(text=f"{val:02X}")

            if self.modified[i]:
                label.config(bg="red", fg="white")
            elif self.accessed[i]:
                label.config(bg="#FFD966", fg="black")
            else:
                label.config(bg="white", fg="black")

        if self.running:
            self.root.after(int(self.poll_interval * 1000), self._update_gui)

if __name__ == "__main__":
    try:
        monitor = EepromMonitor(port=eeprom_mon_port) 
        monitor.start()
    except serial.SerialException as e:
        import tkinter.messagebox as messagebox
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        messagebox.showerror("Serial Port Error", f"Failed to open serial port {eeprom_mon_port}:{e}")
        root.destroy()
