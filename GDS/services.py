# Copyright (c) 2025 MR MODULE PTY LTD
# Licensed under the MIT License

from .definitions import GDSResult
import time

def start_session(core, session_id): # 0x10 - startDiagnosticSession (ref. KWP-GRP-1.5, 6.1.1)
    core.send([0x02, 0x10, session_id]) 
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE  # No reply at all
    # Check for negative response (NRC = 7F + original SID + NRC)
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x10:
        return GDSResult.from_nrc(response[3])  # Convert NRC byte to enum
    # Positive response (0x50 + session ID)
    if response[1] == 0x50 and response[2] == session_id:
        return GDSResult.SUCCESS
    return GDSResult.UNEXPECTED_RESPONSE  # Catch-all for unknown responses


def ecu_reset(core): # 0x11 - ECUReset (ref. KWP-GRP-1.5, 6.5)
    core.send([0x02, 0x11, 0x01])
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x11:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x51:
        time.sleep(0.75)  # Allow time for ECU re-initialization
        return GDSResult.SUCCESS
    return GDSResult.UNEXPECTED_RESPONSE


def clear_dtc(core): # 0x14 - clearDiagnosticInformation (ref. KWP-GRP-1.5, 8.5)
    core.send([0x03, 0x14, 0xFF, 0x00])
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x14:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x54 and response[2] == 0xFF and response[3] == 0x00:
        return GDSResult.SUCCESS
    return GDSResult.UNEXPECTED_RESPONSE


def read_dtc_by_status(core, status=0x00, group=0xFF00, out_data=None): #0x18 - readDiagnosticTroubleCodesByStatus (ref. KWP-GRP-1.5, 8.2.1.1)
    group_high = (group >> 8) & 0xFF
    group_low = group & 0xFF
    data = [0x04, 0x18, status, group_high, group_low]
    
    core.send(data)
    response = core.receive()

    if not response:
        return GDSResult.NO_RESPONSE
    if response[1] == 0x7F and response[2] == 0x18:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x58:
        if out_data is not None:
            out_data.clear()
            out_data.extend(response[2:])  # skip length and SID
        return GDSResult.SUCCESS

    return GDSResult.UNEXPECTED_RESPONSE


def read_data_by_identifier(core, did, out_data): # 0x22 - readDataByCommonIdentifier (ref. KWP-GRP-1.5, 7.2)
    did_high = (did >> 8) & 0xFF
    did_low = did & 0xFF
    core.send([0x03, 0x22, did_high, did_low])
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x22:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x62 and response[2] == did_high and response[3] == did_low:
        out_data.clear()
        expected_len = response[0] - 3  # total len - SID - DID High - DID Low
        out_data.extend(response[4:4 + expected_len])
        return GDSResult.SUCCESS
    return GDSResult.UNEXPECTED_RESPONSE


def write_data_by_identifier(core, did, value_bytes): # 0x2E - writeDataByCommonIdentifier (ref. KWP-GRP-1.5, 7.6)
    if len(value_bytes) > 4:
        return GDSResult.REQUEST_OUT_OF_RANGE
    did_high = (did >> 8) & 0xFF
    did_low = did & 0xFF
    data = [3 + len(value_bytes), 0x2E, did_high, did_low] + value_bytes
    core.send(data)
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x2E:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x6E and response[2] == did_high and response[3] == did_low:
        return GDSResult.SUCCESS
    return GDSResult.UNEXPECTED_RESPONSE


def input_output_control_by_identifier(core, did, control_type, control_data):  # 0x2F - inputOutputControlByCommonIdentifier (ref. KWP-GRP-1.5, 9.2.1)
    """ control_type
            00 = Return Control to ECU
            05 = Freeze Current State
            07 = Short Term Adjustment
    """
    # Accept int or list for control_data
    if isinstance(control_data, int):
        if control_data > 0xFFFFFF:
            return GDSResult.REQUEST_OUT_OF_RANGE
        # Convert int to byte list, MSB first
        control_data = list(control_data.to_bytes((control_data.bit_length() + 7) // 8 or 1, 'big'))
    elif not isinstance(control_data, list):
        return GDSResult.INVALID_ARGUMENT
    
    if len(control_data) > 3:
        return GDSResult.REQUEST_OUT_OF_RANGE

    did_high = (did >> 8) & 0xFF
    did_low = did & 0xFF

    data = [4 + len(control_data), 0x2F, did_high, did_low, control_type] + control_data
    core.send(data)
    response = core.receive()

    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x2F:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x6F and response[2] == did_high and response[3] == did_low:
        return GDSResult.SUCCESS

    return GDSResult.UNEXPECTED_RESPONSE


def read_data_by_local_identifier(core, local_id, out_data): #0x21 - readDataByLocalIdentifier (ref. KWP-GRP-1.5 )
    core.send([0x02, 0x21, local_id])
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x21:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x61 and response[2] == local_id:
        out_data.clear()
        expected_len = response[0] - 2  # total len - SID - LID
        out_data.extend(response[3:3 + expected_len])
        return GDSResult.SUCCESS
    return GDSResult.UNEXPECTED_RESPONSE


def write_data_by_local_identifier(core, local_id, value_bytes): #0x3B - writeDataByLocalIdentifier (ref. KWP-GRP-1.5 )
    if len(value_bytes) > 5:
        # 5 bytes max payload: 1 length + 1 SID + 1 LID + 5 = 8 total
        return GDSResult.REQUEST_OUT_OF_RANGE
    data = [2 + len(value_bytes), 0x3B, local_id] + value_bytes
    core.send(data)
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x3B:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x7B and response[2] == local_id:
        return GDSResult.SUCCESS
    return GDSResult.UNEXPECTED_RESPONSE

def read_memory_by_address(core, address, length, out_data):  #0x23 - readMemoryByAddress (ref. KWP-GRP-1.5, 7.3)
    if not (0 <= address <= 0xFFFFFFFF):
        return GDSResult.REQUEST_OUT_OF_RANGE
    if not (1 <= length <= 0x4094):
        return GDSResult.REQUEST_OUT_OF_RANGE

    addr_bytes = [
        (address >> 24) & 0xFF,
        (address >> 16) & 0xFF,
        (address >> 8) & 0xFF,
        address & 0xFF
    ]
    len_high = (length >> 8) & 0xFF
    len_low = length & 0xFF

    data = [0x07, 0x23] + addr_bytes + [len_high, len_low]
    core.send(data)
    response = core.receive()

    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x23:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x63:
        expected_len = response[0] - 1  # SID is 1 byte
        out_data.clear()
        out_data.extend(response[2:2 + expected_len])
        return GDSResult.SUCCESS

    return GDSResult.UNEXPECTED_RESPONSE


def write_memory_by_address(core, address, values): #0x3D - writeMemoryByAddress (ref. KWP-GRP-1.5, 7.7)
    if not (0 <= address <= 0xFFFFFFFF):
        return GDSResult.REQUEST_OUT_OF_RANGE
    if not (1 <= len(values) <= 4088):
        return GDSResult.REQUEST_OUT_OF_RANGE

    addr_bytes = [
        (address >> 24) & 0xFF,
        (address >> 16) & 0xFF,
        (address >> 8) & 0xFF,
        address & 0xFF
    ]
    len_high = (len(values) >> 8) & 0xFF
    len_low = len(values) & 0xFF

    data = [0x07 + len(values), 0x3D] + addr_bytes + [len_high, len_low] + values
    core.send(data)
    response = core.receive()

    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x3D:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x7D and response[2:6] == addr_bytes:
        return GDSResult.SUCCESS

    return GDSResult.UNEXPECTED_RESPONSE


def tester_present(core, response_required=True): #0x3E - testerPresent (ref. KWP-GRP-1.5, 6.4)
    subfunction = 0x01 if response_required else 0x02
    core.send([0x02, 0x3E, subfunction])
    if not response_required:
        return GDSResult.SUCCESS  # No reply expected
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x3E:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x7E:
        return GDSResult.SUCCESS
    return GDSResult.UNEXPECTED_RESPONSE


def request_download(core, address, size): #0x34 - requestDownload (ref. KWP-GRP-1.5, 11.1.2)
    if not (0 <= address <= 0xFFFFFFFF):
        return GDSResult.REQUEST_OUT_OF_RANGE
    if not (0 < size <= 0xFFFFFF):
        return GDSResult.REQUEST_OUT_OF_RANGE

    addr_bytes = [
        (address >> 24) & 0xFF,
        (address >> 16) & 0xFF,
        (address >> 8) & 0xFF,
        address & 0xFF
    ]

    size_bytes = [
        (size >> 16) & 0xFF,
        (size >> 8) & 0xFF,
        size & 0xFF
    ]

    dfi = 0x00  # no compression or encryption

    data = [0x09, 0x34] + addr_bytes + [dfi] + size_bytes
    core.send(data)

    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[1] == 0x7F and response[2] == 0x34:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x74:
        return GDSResult.SUCCESS

    return GDSResult.UNEXPECTED_RESPONSE


def request_upload(core, address, size): #0x35 - requestUpload (ref. KWP-GRP-1.5, 11.2.2)
    if not (0 <= address <= 0xFFFFFFFF):
        return GDSResult.REQUEST_OUT_OF_RANGE
    if not (1 <= size <= 0xFFFFFF):
        return GDSResult.REQUEST_OUT_OF_RANGE

    addr_bytes = [
        (address >> 24) & 0xFF,
        (address >> 16) & 0xFF,
        (address >> 8) & 0xFF,
        address & 0xFF,
    ]

    size_bytes = [
        (size >> 16) & 0xFF,
        (size >> 8) & 0xFF,
        size & 0xFF,
    ]

    dfi = 0x00  # no compression

    data = [0x09, 0x35] + addr_bytes + [dfi] + size_bytes
    core.send(data)

    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[1] == 0x7F and response[2] == 0x35:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x75:
        return GDSResult.SUCCESS

    return GDSResult.UNEXPECTED_RESPONSE


def transfer_data(core, block_number, out_data): #0x36 - transferData (ref. KWP-GRP-1.5, 11.3.1)
    core.send([0x02, 0x36, block_number])
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[1] == 0x7F and response[2] == 0x36:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x76 and response[2] == block_number:
        out_data.clear()
        out_data.extend(response[3:])
        return GDSResult.SUCCESS

    return GDSResult.UNEXPECTED_RESPONSE


def request_transfer_exit(core): #0x37 - requestTransferExit (ref. KWP-GRP-1.5, 11.4.2)
    core.send([0x01, 0x37])
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[1] == 0x7F and response[2] == 0x37:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x77:
        return GDSResult.SUCCESS

    return GDSResult.UNEXPECTED_RESPONSE