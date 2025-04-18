# Copyright (c) 2025 MR MODULE PTY LTD
# Licensed under the MIT License

import can
import msvcrt  # Windows-only
from GDS import FordGDS, logger  # You may need to implement this if not already
from eeprom_monitor import EepromMonitor

can_com_port = 'COM10'
can_bitrate = 500000
eeprom_mon_port = 'COM14'

id_masks = {
    0x200: b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
    0x207: b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
    0x230: b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
    0x427: b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
    0x623: b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
    0x640: b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
    0x6F6: b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
    0x403: b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
    0x307: b'\xFF\xFF\xFF\xFF\xFF\x00\x00\xFF',
    0x353: b'\xFF\xFF\xFF\xFF\x00\x00\x00\xFF',
    0x437: b'\xFF\xFF\xFF\xFF\x00\xFF\xFF\xFF',
    0x500: b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
    0x553: b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF',
}

# Track last seen data bytes for each CAN ID
last_seen_data = {}

def is_data_changed(msg):
    global last_seen_data

    can_id = msg.arbitration_id
    current_data = msg.data
    mask = id_masks.get(can_id, b'\xFF' * len(current_data))  # Default: all bits matter

    last_data = last_seen_data.get(can_id)
    if last_data is None:
        last_seen_data[can_id] = current_data
        return True
    
    # XOR to find changed bits
    diff = bytes([a ^ b for a, b in zip(current_data, last_data)])

    # Apply mask — zero out masked bits
    relevant_change = bytes([d & m for d, m in zip(diff, mask)])

    if all(b == 0 for b in relevant_change):
        return False
    
    last_seen_data[can_id] = current_data
    return True


def monitor():
    # Create CAN bus instance (adjust channel/interface if needed)
    bus = can.interface.Bus(interface='csscan_serial', channel=can_com_port, bitrate=can_bitrate)  # adjust as needed

    # Create HTML log file
    logfile = open(logger.generate_log_filename(), "w")
    logger.begin(logfile)

    # Start EEPROM visual debugger
    eeprom_monitor = EepromMonitor(port=eeprom_mon_port)  # Change COM port as needed
    eeprom_monitor.start()

    try:
        while True:
            if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'`':
                        print("⏹️  Exit key pressed. Stopping.")
                        break

            msg = bus.recv()
            if msg is None:
                continue

            is_gds = FordGDS.is_gds_message(msg)

            if is_gds or is_data_changed(msg):
                logger.log(msg)

    finally:
        bus.shutdown()
        eeprom_monitor.stop()

if __name__ == "__main__":
    monitor()
