# Copyright (c) 2025 MR MODULE PTY LTD
# Licensed under the MIT License

from enum import Enum


BROADCAST_MODULE_ID = {
    0x200: "PCM",
    0x207: "PCM",
    0x230: "PCM",
    0x427: "PCM",
    0x623: "PCM",
    0x640: "PCM",
    0x6F6: "PCM IMMO",
    0x403: "BEM",
    0x6F8: "BEM IMMO",
    0x307: "ACM",
    0x353: "HIM",
    0x437: "IC",
    0x500: "IC",
    0x553: "IC"
}

GDS_MODULE_ID = {
    'PCM': {'req_id': 0x7E0, 'resp_id': 0x7E8},
    'OBD2': {'req_id': 0x7DF, 'resp_id': 0x7E8},
    'BEM': {'req_id': 0x726, 'resp_id': 0x72E},
    'IC':  {'req_id': 0x720, 'resp_id': 0x728},
    'HIM': {'req_id': 0x733, 'resp_id': 0x73B},
    'ACM': {'req_id': 0x727, 'resp_id': 0x72F},
    'ABS': {'req_id': 0x760, 'resp_id': 0x768} # may not be for BA, on KLINE?
    # Add more modules as needed
    # eg. 'TCM': {'req': 0x7E1, 'resp': 0x7E9},
}

GDS_SERVICE_ID = {
    0x01: "OBD2 - Current Data",
    0x02: "OBD2 - Freeze Frame Data",
    0x03: "OBD2 - Show Stored DTCs",
    0x04: "OBD2 - Clear DTCs",
    0x05: "OBD2 - Oxygen Sensor Monitoring",
    0x06: "OBD2 - On Board Monitoring",
    0x07: "OBD2 - Pending DTCs",
    0x08: "OBD2 - Control Component",
    0x09: "OBD2 - Vehicle Info",
    0x10: "Start Diagnostic Session",
    0x11: "ECU Reset",
    0x14: "Clear DTCs",
    0x18: "Read DTC By Status",
    0x21: "Read Local ID",
    0x22: "Read Common ID",
    0x23: "Read Memory By Address",
    0x27: "Security Access",
    0x2E: "Write Common ID",
    0x2F: "Input Output Control by Common ID",
    0x3B: "Write Local ID",
    0x3D: "Write Memory By Address",
    0x3E: "Tester Present",
    0x7F: "Negative Response"
}


class GDSResult(Enum):
    # Values > 0xFF cannot be confused with NRC byte values
    SUCCESS = 0x100
    NO_RESPONSE = 0x101
    UNEXPECTED_RESPONSE = 0x102
    OTHER_NEGATIVE_RESPONSE = 0x103
    NOT_YET_IMPLEMENTED = 0x104
    INVALID_ARGUMENT = 0x105
    # NRC-specific codes (match byte values from ECU)
    GENERAL_REJECT = 0x10
    SERVICE_NOT_SUPPORTED = 0x11
    INVALID_FORMAT = 0x12
    CONDITIONS_NOT_CORRECT = 0x22
    REQUEST_OUT_OF_RANGE = 0x31
    SECURITY_ACCESS_DENIED = 0x33
    INVALID_KEY = 0x35

    def __str__(self):
        return self.name.replace('_', ' ').title()

    @classmethod
    def from_nrc(cls, code):
        for result in cls:
            if result.value == code:
                return result
        return cls.OTHER_NEGATIVE_RESPONSE
    
class GDSSession:
    DIAGNOSTIC = 0x81
    PROGRAMMING = 0x85
    ADJUSTMENT = 0x87
    @classmethod
    def to_str(cls, session_id):
        mapping = {
            cls.DIAGNOSTIC: "Standard Diagnostic",
            cls.PROGRAMMING: "ECU Programming",
            cls.ADJUSTMENT: "ECU Adjustment"
        }
        return mapping.get(session_id, f"Unknown Session ({session_id:#04X})")