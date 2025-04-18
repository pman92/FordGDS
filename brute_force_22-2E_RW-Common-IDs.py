# Copyright (c) 2025 MR MODULE PTY LTD
# Licensed under the MIT License

import can, time, os, csv
import msvcrt  # Windows-only
from datetime import datetime
from GDS import FordGDS, GDSResult, GDSSession, logger
from eeprom_monitor import EepromMonitor

# Settings
can_com_port = 'COM10'
can_bitrate = 500000
eeprom_mon_port = 'COM14'
module_id = 'ACM'
start_read_id = 0x0000
start_write_id = 0x0000
eeprom_activity_pause = 6 # Number of seconds to pause if eeprom activity detected
max_attempts_each_id = 5 #Max attempts at each ID with no response received


# Track last seen data bytes for each CAN ID, only log when they change
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




csv_headers = [
    "DID", "Read/Write", "NRC", "ReadData", "WriteData",
    "EEPROM Access/Modify", "EEPROM Address", "EEPROM Data"
]


# Brute force check of all ID's:
def brute_force_check():
    # Create CAN bus instance
    bus = can.interface.Bus(interface='csscan_serial', channel=can_com_port, bitrate=can_bitrate)  # adjust as needed

    # Start Logging CAN data
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_dir = "brute_force_log"
    os.makedirs(log_dir, exist_ok=True)
    
    #logfile = open(os.path.join(log_dir, f"log_{timestamp}.html"), "w") 
    logfile = None # Dont log CAN data to HTML
    logger.begin(logfile)

    # Create CSV log file for DIDs
    csv_path = os.path.join(log_dir, f"did_results_{timestamp}.csv")
    csv_file = open(csv_path, mode='w', newline='')
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(csv_headers)

    # EEPROM callbacks
    eeprom_monitor = EepromMonitor(port=eeprom_mon_port)  # Change COM port as needed
    eeprom_activity_detected = False # Used to delay DID scanning during EEPROM activity
    eeprom_pause_until = 0  
    def eeprom_access(addr, value):
        nonlocal eeprom_pause_until, eeprom_activity_detected
        logger.log(f"    EEPROM access: ADR 0x{addr:02X} = 0x{value:02X}")
        csv_writer.writerow(["", "", "", "", "", "Access", f"0x{addr:02X}", f"0x{value:02X}"])
        csv_file.flush()
        eeprom_pause_until = time.time() + eeprom_activity_pause
        eeprom_activity_detected = True

    def eeprom_modify(addr, value):
        nonlocal eeprom_pause_until, eeprom_activity_detected
        logger.log(f"    EEPROM write: ADR 0x{addr:02X} = 0x{value:02X}")
        csv_writer.writerow(["", "", "", "", "", "Modify", f"0x{addr:02X}", f"0x{value:02X}"])
        csv_file.flush()
        eeprom_pause_until = time.time() + eeprom_activity_pause
        eeprom_activity_detected = True

    eeprom_monitor.on_accessed = eeprom_access
    eeprom_monitor.on_modified = eeprom_modify

    # Start EEPROM visual debugger to monitor EEPROM state
    eeprom_monitor.start()
    eeprom_monitor._clear_flags()

    # Start GDS Instance
    gds = FordGDS(bus)

    # Set Module
    gds.set_module(module_id)

    # Init loop values
    read_did = start_read_id
    write_did = start_write_id
    
    try:
        while True:
            os.system('cls')  # Clear terminal output

            # "`"" key pressed to end script:
            if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'`':
                        print("⏹️  Exit key pressed. Stopping.")
                        break

            # log CAN traffic:
            msg = bus.recv()
            if msg is None:
                continue
            is_gds = FordGDS.is_gds_message(msg)
            if is_gds or is_data_changed(msg):
                logger.log(msg)

            if time.time() < eeprom_pause_until:
                print("Waiting for any further EEPROM activity")
                time.sleep(1)
                continue  # Still waiting for EEPROM activity to settle
            elif eeprom_activity_detected:
                eeprom_monitor._clear_flags()
                eeprom_activity_detected = False

            # Move through CAN ID's and try each of them:
            if read_did <= 0xFFFF:
                did_high = (read_did >> 8) & 0xFF
                did_low = read_did & 0xFF
                gds.send([0x03, 0x22, did_high, did_low])

                response = gds.receive()
                if response:
                    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x22:
                        if(response[3] != 0x31):
                            # A response other than Request Out Of Range, log it to a file here
                            csv_writer.writerow([
                                f"{read_did:04X}", "Read", f"{response[3]:02X}", "", "", "", "", ""
                            ])
                            csv_file.flush()
                            time.sleep(2)
                    if response[1] == 0x62 and response[2] == did_high and response[3] == did_low:
                        # A positive response
                        expected_len = response[0] - 3
                        out_data = response[4:4 + expected_len]
                        hex_out = ' '.join(f"{b:02X}" for b in out_data)
                        csv_writer.writerow([
                            f"{read_did:04X}", "Read", "", hex_out, "", "", "", ""
                        ])
                        csv_file.flush()
                        time.sleep(2)
                    read_did += 1
                    attempts_on_id = 0
                else:
                    attempts_on_id += 1
                    if(attempts_on_id >= max_attempts_each_id):
                        read_did += 1

            elif write_did <= 0xFFFF:
                did_high = (write_did >> 8) & 0xFF
                did_low = write_did & 0xFF
                gds.send([0x04, 0x2E, did_high, did_low, 0x00])

                response = gds.receive()
                if response:
                    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x2E:
                        if(response[3] != 0x31):
                            # A response other than Request Out Of Range, log it to a file
                            csv_writer.writerow([
                                f"{write_did:04X}", "Write", f"{response[3]:02X}", "", "", "", "", ""
                            ])
                            csv_file.flush()
                            time.sleep(2)
                    if response[1] == 0x6E and response[2] == did_high and response[3] == did_low:
                        # A positive response, log it to a file
                        csv_writer.writerow([
                            f"{write_did:04X}", "Write", "", "", "00", "", "", ""
                        ])
                        csv_file.flush()
                        time.sleep(2)
                    write_did += 1
                    attempts_on_id = 0
                else:
                    attempts_on_id += 1
                    if(attempts_on_id >= max_attempts_each_id):
                        write_did += 1

            else:
                break # All DID's checked
                
            time.sleep(0.15)

    except Exception as e:
        # Save crash log
        crash_log_path = os.path.join(log_dir, f"crash_log_{timestamp}.txt")
        current_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        with open(crash_log_path, "w") as f:
            f.write("Brute-force script crashed!\n\n")
            f.write(f"Crash Time: {current_timestamp}\n")
            f.write(f"Exception: {repr(e)}\n")
            f.write(f"Last read_did: 0x{read_did:04X}\n")
            f.write(f"Last write_did: 0x{write_did:04X}\n")
        print(f"\n💥 Script Crashed! ")
        print(f"\n💥 Crash logged to: {crash_log_path}")

    finally:
        try:
            gds.close()
        except:
            pass
        try:
            eeprom_monitor.stop()
        except:
            pass
        try:
            csv_file.close()
        except:
            pass

if __name__ == "__main__":
    brute_force_check()

