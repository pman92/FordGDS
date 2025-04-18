# Copyright (c) 2025 MR MODULE PTY LTD
# Licensed under the MIT License

from .definitions import GDSResult

def security_access_request_seed(core, out_data):
    core.send([0x02, 0x27, 0x01])
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x27:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x67 and response[2] == 0x01:
        out_data.clear()
        expected_len = response[0] - 2  # total len - SID - Subfunction
        out_data.extend(response[3:3 + expected_len])
        return GDSResult.SUCCESS
    return GDSResult.UNEXPECTED_RESPONSE

def security_access_send_key(core, key_bytes):
    core.send([0x03 + len(key_bytes), 0x27, 0x02] + key_bytes)
    response = core.receive()
    if not response:
        return GDSResult.NO_RESPONSE
    if response[0] >= 0x03 and response[1] == 0x7F and response[2] == 0x27:
        return GDSResult.from_nrc(response[3])
    if response[1] == 0x67 and response[2] == 0x02:
        return GDSResult.SUCCESS
    return GDSResult.UNEXPECTED_RESPONSE

"""
You may want to add related functions here as well, eg. key calculation?
"""