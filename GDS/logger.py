# Copyright (c) 2025 MR MODULE PTY LTD
# Licensed under the MIT License

import time
import os
import can
import csv

from GDS.FordGDS import FordGDS
from .definitions import GDS_MODULE_ID, GDS_SERVICE_ID, BROADCAST_MODULE_ID, GDSSession, GDSResult

_html_file = None
_csv_file = None
_csv_writer = None
_warned_once = False

def _timestamp():
    return time.strftime('%H:%M:%S', time.localtime()) + f".{int(time.time() * 1000) % 1000:03d}"

def generate_log_filename():
    datestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, f"log_{datestamp}.html")

def begin(file = None):
    global _html_file, _csv_file, _csv_writer
    
    if file is not None:
        _html_file = file
        _html_file.write("<html><body><pre>\n")
        csv_path = os.path.splitext(file.name)[0] + ".csv"
    else:
        filename = generate_log_filename()  # returns a string path
        csv_path = os.path.splitext(filename)[0] + ".csv"

    _csv_file = open(csv_path, "w", newline="")
    _csv_writer = csv.writer(_csv_file)
    _csv_writer.writerow(["Timestamp", "Direction", "ID", "Byte0", "Byte1", "Byte2", "Byte3", "Byte4", "Byte5", "Byte6", "Byte7", "Description"])


def end():
    global _html_file, _csv_file
    if _html_file:
        _html_file.write("</pre></body></html>\n")
        _html_file.close()
        _html_file = None
    if _csv_file:
        _csv_file.close()
        _csv_file = None


def log(msg, direction="  "):
    timestamp = _timestamp()
    GREY = "\033[90m"
    RESET = "\033[0m"

    if isinstance(msg, can.Message):
        terminal_message(msg, direction, timestamp)
        html_message(msg, direction, timestamp)
        csv_message(msg, direction, timestamp)
    elif isinstance(msg, list) and all(isinstance(b, int) and 0 <= b <= 0xFF for b in msg):
        # List of bytes (e.g. raw response frame)
        data_str = ' '.join(f"{b:02X}" for b in msg)
        print(f"{GREY}[{timestamp}]{RESET} {direction} {data_str}")
        html_text(f"{direction} {data_str}", timestamp)
    elif isinstance(msg, str):
        print(f"{GREY}[{timestamp}]{RESET} {msg}")
        html_text(msg, timestamp)

def terminal_message(msg, direction="  ", timestamp=None):
    RESET = "\033[0m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"
    GREY = "\033[90m"
    ORANGE = "\033[38;5;208m"

    if timestamp is None:
        timestamp = _timestamp()

    is_gds = FordGDS.is_gds_message(msg)
    pci = msg.data[0] >> 4
    id_color = GREEN if is_gds else CYAN
    print(f"{GREY}[{timestamp}]{RESET} {direction} {id_color}{msg.arbitration_id:03X}{RESET}", end=" | ")

    for i, byte in enumerate(msg.data):
        if not is_gds:
            color = RESET
        elif pci == 0x1:
            if i == 0:
                color = ORANGE
            elif i == 1:
                color = MAGENTA  # Length byte
            elif i == 2:
                color = CYAN # Echo of request SID with +0x40
            else:
                color = YELLOW
        elif pci == 0x2:
            color = ORANGE if i == 0 else YELLOW
        elif pci == 0x3:
            color = ORANGE if i == 0 else GREY
        elif i == 0:
            color = MAGENTA  # Length
        elif i == 1:
            color = CYAN  # SID
        elif i > msg.data[0]:
            color = GREY  # Padding
        else:
            color = YELLOW  # Params
        print(f"{color}{byte:02X}{RESET}", end=" ")

    if is_gds:
        print(f"| {RESET}{get_sid_description(msg)}{RESET}")
    else:
        print(f"| {RESET}{get_broadcast_description(msg)}{RESET}")


def html_message(msg, direction="  ", timestamp=None):
    global _warned_once, _html_file
    if _html_file is None:
        if not _warned_once:
            print("HTML log file not set, skipping HTML log output.")
            _warned_once = True
        return
    
    if timestamp is None:
        timestamp = _timestamp()
    
    def color_span(byte_str, color):
        return f'<span style="color:{color}">{byte_str}</span>'

    
    is_gds = FordGDS.is_gds_message(msg)
    pci = msg.data[0] >> 4
    html = f'<div><span style="color:#666">[{timestamp}]</span> <strong>{direction} {msg.arbitration_id:03X}</strong> | '

    for i, byte in enumerate(msg.data):
        if not is_gds:
            color = "#000000"
        elif pci == 0x1:
            if i == 0:
                color = "#C05000"  # Orange
            elif i == 1:
                color = "#D58AF5"  # Magenta (Length)
            elif i == 2:
                color = "#00C0F0"  # Cyan (echo of reuqest SID)
            else:
                color = "#FF8C00"
        elif pci == 0x2:
            color = "#C05000" if i == 0 else "#FF8C00"
        elif pci == 0x3:
            color = "#C05000" if i == 0 else "#AAAAAA"
        elif i == 0:
            color = "#D58AF5"  # length = magenta
        elif i == 1:
            color = "#00C0F0"  # SID = cyan
        elif i > msg.data[0]:
            color = "#AAAAAA"  # padding = grey
        else:
            color = "#FF8C00"  # parameter = darker orange
        html += color_span(f"{byte:02X}", color) + " "

    if is_gds:
        html += f"| <span style='color:#000'>{get_sid_description(msg)}</span>"
    else:
        html += f"| <span style='color:#000'>{get_broadcast_description(msg)}</span>"

    html += "</div>\n"

    _html_file.write(html)


def html_text(text, timestamp=None):
    global _html_file, _warned_once
    if _html_file is None:
        if not _warned_once:
            print("⚠️  HTML log file not set, skipping HTML log output.")
            _warned_once = True
        return
    if timestamp is None:
        timestamp = _timestamp()
    _html_file.write(f"<div><span style='color:#666'>[{timestamp}]</span> {text}</div> \n")


def csv_message(msg, direction="  ", timestamp=None):
    global _csv_writer
    if not _csv_writer:
        return

    if timestamp is None:
        timestamp = _timestamp()

    if FordGDS.is_gds_message(msg):
        desc = get_sid_description(msg)
    else:
        desc = get_broadcast_description(msg)
    row = [timestamp, direction, f"{msg.arbitration_id:03X}"]
    row.extend(f"{b:02X}" for b in msg.data)
    row += [""] * (8 - len(msg.data))  # Pad empty bytes
    row.append(desc)
    _csv_writer.writerow(row)


def get_sid_description(msg):
    sid = msg.data[1] if len(msg.data) > 1 else None
    req_sid = sid - 0x40 if sid and sid >= 0x40 else None

    if (msg.data[0] >> 4) == 0x1:
        length = ((msg.data[0] & 0x0F) << 8) | msg.data[1]
        return f"Multiframe - {length} bytes"
    elif (msg.data[0] >> 4) == 0x2:
        return "Multiframe - Consecutive"
    elif (msg.data[0] >> 4) == 0x3:
        return "Multiframe - Flow Control"
    
    if sid == 0x7F and msg and len(msg.data) >= 4:
        nrc = msg.data[3]
        reason = str(GDSResult.from_nrc(nrc))
        return f"NR - {reason}"
    
    # Request SIDs:
    if sid == 0x10 and len(msg.data) >= 3:
        session = msg.data[2]
        detail = GDSSession.to_str(session)
        return f"Start Diagnostic Session - {detail}"
    elif sid == 0x21 and len(msg.data) >= 3:
        return f"Read Local ID 0x{msg.data[2]:02X}"
    elif sid == 0x22 and len(msg.data) >= 4:
        return f"Read Common ID 0x{msg.data[2]:02X}{msg.data[3]:02X}"
    elif sid == 0x2E and len(msg.data) >= 4:
        return f"Write Common ID 0x{msg.data[2]:02X}{msg.data[3]:02X}"
    elif sid == 0x2F and len(msg.data) >= 5:
        cid = f"0x{msg.data[2]:02X}{msg.data[3]:02X}"
        control_option = msg.data[4]
        control_text = {
            0x00: "Return Control to ECU",
            0x05: "Freeze Current State",
            0x07: "Short Term Adjustment"
        }.get(control_option, f"Unknown (0x{control_option:02X}) Control Type")
        
        expected_param_bytes = msg.data[0] - 4  # subtract header bytes: SID, DID high/low, control_type
        param_bytes = msg.data[5:5 + expected_param_bytes]
        params = param_bytes.hex().upper() if param_bytes else ""
        return (
            f"Input/Output Control - Common ID {cid}, "
            f"{control_text}"
            + (f", Data={params}" if params else "")
        )
    elif sid == 0x3B and len(msg.data) >= 3:
        return f"Write Local ID 0x{msg.data[2]:02X}"
    elif sid == 0x23 and len(msg.data) >= 7:
        addr = (msg.data[2] << 24) | (msg.data[3] << 16) | (msg.data[4] << 8) | msg.data[5]
        size = (msg.data[6] << 8) | msg.data[7]
        return f"Read Memory 0x{addr:08X} ({size} bytes)"
    elif sid == 0x3D and len(msg.data) >= 8:
        addr = (msg.data[2] << 24) | (msg.data[3] << 16) | (msg.data[4] << 8) | msg.data[5]
        size = (msg.data[6] << 8) | msg.data[7]
        return f"Write Memory 0x{addr:08X} ({size} bytes)"
    elif sid == 0x3E and len(msg.data) >= 3:
        resp_required = msg.data[2]
        resp_text = "Response Required" if resp_required == 0x01 else "No Response"
        return f"Tester Present - {resp_text}"

    # Positive Response SIDs:
    if req_sid in GDS_SERVICE_ID:
        if req_sid == 0x27 and len(msg.data) > 3:
            # Security Access Key Sent (SID = 0x67, sub = 0x02)
            if msg.data[2] == 0x02:
                return "OK - Key Accepted"
            # Security Access Seed Response (SID = 0x67, sub = 0x01)
            elif msg.data[2] == 0x01:
                seed_bytes = msg.data[3:3 + (msg.data[0] - 2)]
                seed_str = ' '.join(f"{b:02X}" for b in seed_bytes)
                return f"OK - Seed: {seed_str}"
        elif req_sid == 0x21 and len(msg.data) > 3:
            value = ' '.join(f"{b:02X}" for b in msg.data[3:3 + (msg.data[0] - 2)])
            return f"OK - {value}"
        elif req_sid == 0x22 and len(msg.data) > 4:
            did = f"{msg.data[2]:02X}{msg.data[3]:02X}"
            value = ' '.join(f"{b:02X}" for b in msg.data[4:4 + (msg.data[0] - 3)])
            return f"OK - DID {did} = {value}"
        elif req_sid == 0x23:
            raw_bytes = msg.data[2:2 + (msg.data[0] - 1)]
            value = ' '.join(f"{b:02X}" for b in raw_bytes)
            ascii_str = ''.join(chr(b) if 0x20 <= b <= 0x7E else '.' for b in raw_bytes)
            return f"OK - Memory Read = {value} (\"{ascii_str}\")"
        elif req_sid == 0x3D:
            addr = (msg.data[2] << 24) | (msg.data[3] << 16) | (msg.data[4] << 8) | msg.data[5]
            return f"OK - Memory Written at 0x{addr:08X}"
        return f"OK"
    
    # Default:
    return GDS_SERVICE_ID.get(sid, "???")


def get_broadcast_description(msg):
    if msg.arbitration_id in BROADCAST_MODULE_ID:
        return BROADCAST_MODULE_ID.get(msg.arbitration_id)