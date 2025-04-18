# Copyright (c) 2025 MR MODULE PTY LTD
# Licensed under the MIT License

import time
import can
from .definitions import GDS_MODULE_ID

GDS_IDS = {mod['req_id'] for mod in GDS_MODULE_ID.values()} | {mod['resp_id'] for mod in GDS_MODULE_ID.values()} # cache IDs for faster lookup

from .definitions import GDS_MODULE_ID, GDS_SERVICE_ID, GDSResult, GDSSession
from .services import (
    start_session,
    ecu_reset,
    clear_dtc,
    read_dtc_by_status,
    read_data_by_identifier,
    write_data_by_identifier,
    input_output_control_by_identifier,
    read_data_by_local_identifier,
    write_data_by_local_identifier,
    read_memory_by_address,
    write_memory_by_address,
    tester_present,
    request_download,
    request_upload,
    transfer_data,
    request_transfer_exit
)
from .security_access import (
    security_access_request_seed,
    security_access_send_key
)

class FordGDS:
    def __init__(self, bus):
        if bus is None:
            raise ValueError("GDS: A valid CAN bus instance must be provided.")
        self.bus = bus
        self.req_id = None
        self.resp_id = None

    @staticmethod
    def is_gds_message(msg: can.Message) -> bool:
        """Returns True if the message arbitration_id matches a known GDS request/response ID."""
        return msg.arbitration_id in GDS_IDS

    @staticmethod
    def is_gds_service(msg: can.Message) -> bool:
        """Returns True if the message data 0 byte matches a GDS service ID"""
        return len(msg.data) > 0 and msg.data[0] in GDS_SERVICE_ID

    def set_module(self, module_name):
        if module_name not in GDS_MODULE_ID:
            raise ValueError(f"GDS: Unknown module: {module_name}")
        self.req_id = GDS_MODULE_ID[module_name]['req_id']
        self.resp_id = GDS_MODULE_ID[module_name]['resp_id']

    def send(self, data):
        from . import logger
        if self.req_id is None:
            raise ValueError("GDS: Request ID not set. Call set_module() first.")
        if len(data) <= 8:
            msg = can.Message(arbitration_id=self.req_id, data=data + [0x00] * (8 - len(data)), is_extended_id=False)
            self.bus.send(msg)
            logger.log(msg, "TX")
        else:
            return self.send_multiframe(data)

    def receive(self, timeout=1.0):
        if self.resp_id is None:
            raise ValueError("GDS: Response ID not set. Call set_module() first.")
        return self.receive_multiframe(timeout)
    
    def receive_raw(self, timeout=1.0):
        from . import logger
        start_time = time.time()
        while time.time() - start_time < timeout:
            msg = self.bus.recv(timeout=0.05)
            if msg and msg.arbitration_id == self.resp_id:
                logger.log(msg, "RX")
                return msg
        return None
    
    def send_multiframe(self, data):
        total_len = len(data)
        first_frame = [0x10 | ((total_len >> 8) & 0x0F), total_len & 0xFF] + data[:6]
        self.send(first_frame)

        flow = None
        flow_timeout = time.time() + 1.0  # 1 second max wait for flow control
        while time.time() < flow_timeout:
            candidate = self.receive_raw()
            if candidate and candidate.data[0] == 0x30:
                flow = candidate.data
                break
        if not flow:
            return GDSResult.NO_RESPONSE
        
        block_size = flow[1]
        stmin_raw = flow[2]

        # Interpret STmin per ISO 15765-2
        if 0x00 <= stmin_raw <= 0x7F:
            stmin = stmin_raw / 1000.0
        elif 0xF1 <= stmin_raw <= 0xF9:
            stmin = (stmin_raw - 0xF0) / 10000.0
        else:
            stmin = 0  # Treat unknown values as 0 delay

        seq = 1
        frames_sent = 0
        remaining = data[6:]

        time.sleep(stmin)

        while remaining:
            # Send up to `block_size` consecutive frames before waiting for next FC
            for _ in range(block_size or 0xFFFF):  # if block_size = 0, unlimited
                if not remaining:
                    break
                chunk = remaining[:7]
                remaining = remaining[7:]

                frame = [0x20 | (seq & 0x0F)] + chunk
                frame += [0x00] * (8 - len(frame))  # pad to 8 bytes
                self.send(frame)
                time.sleep(stmin)

                seq = (seq + 1) % 0x10
                frames_sent += 1

            if remaining and block_size != 0:
                # Wait for another Flow Control frame
                flow = None
                flow_timeout = time.time() + 1.0
                while time.time() < flow_timeout:
                    candidate = self.receive_raw()
                    if candidate and candidate.data[0] == 0x30:
                        flow = candidate.data
                        break

                if not flow:
                    return GDSResult.NO_RESPONSE

                # Update STmin and BlockSize again in case they change
                block_size = flow[1]
                stmin_raw = flow[2]

                if 0x00 <= stmin_raw <= 0x7F:
                    stmin = stmin_raw / 1000.0
                elif 0xF1 <= stmin_raw <= 0xF9:
                    stmin = (stmin_raw - 0xF0) / 10000.0
                else:
                    stmin = 0
        GDSResult.SUCCESS

    def receive_multiframe(self, timeout=1.0):
        from . import logger
        start_time = time.time()
        full_data = []
        expected_len = None
        seq = 1

        while time.time() - start_time < timeout:
            msg = self.bus.recv(timeout=0.05)
            if not msg or msg.arbitration_id != self.resp_id:
                continue

            logger.log(msg, "RX")
            data = list(msg.data)
            pci = data[0]

            if pci >> 4 == 0x0:
                return data

            elif pci >> 4 == 0x1:
                expected_len = ((pci & 0x0F) << 8) | data[1]
                full_data = data[2:]
                self.send([0x30, 0x00, 0x00] + [0x00] * 5)

            elif pci >> 4 == 0x2:
                if (pci & 0x0F) != seq:
                    logger.log(f"Unexpected sequence number: expected {seq}, got {(pci & 0x0F)}")
                    break
                seq = (seq + 1) % 0x10
                full_data += data[1:]
                if expected_len and len(full_data) >= expected_len:
                    result_data = full_data[:expected_len]
                    return [expected_len] + result_data

        return None

    def start_session(self, session_id):
        return start_session(self, session_id)
    
    def ecu_reset(self):
        return ecu_reset(self)
    
    def clear_dtc(self):
        return clear_dtc(self)
    
    def read_dtc_by_status(core, status=0x00, group=0xFF00, out_data=None):
        return read_dtc_by_status(core, status=0x00, group=0xFF00, out_data=None)

    def read_data_by_identifier(self, did, out_data):
        return read_data_by_identifier(self, did, out_data)

    def write_data_by_identifier(self, did, value_bytes):
        return write_data_by_identifier(self, did, value_bytes)

    def read_data_by_local_identifier(self, local_id, out_data):
        return read_data_by_local_identifier(self, local_id, out_data)
    
    def write_data_by_local_identifier(self, did, value_bytes):
        return write_data_by_local_identifier(self, did, value_bytes)
    
    def input_output_control_by_identifier(core, did, control_type, control_data):
        return input_output_control_by_identifier(core, did, control_type, control_data)
    
    def read_memory_by_address(core, address, length, out_data):
        return read_memory_by_address(core, address, length, out_data)
    
    def write_memory_by_address(core, address, values):
        return write_memory_by_address(core, address, values)

    def security_access_request_seed(self, out_data):
        return security_access_request_seed(self, out_data)

    def security_access_send_key(self, key_bytes):
        return security_access_send_key(self, key_bytes)
    
    def tester_present(core, response_required=True):
        return tester_present(core, response_required)

    def request_download(core, address, size):
        return request_download(core, address, size)
    
    def request_upload(core, address, size):
        return request_upload(core, address, size)
    
    def transfer_data(core, block_number, out_data):
        return transfer_data(core, block_number, out_data)
    
    def request_transfer_exit(core):
        return request_transfer_exit(core)

    def close(self):
        from . import logger
        self.bus.shutdown()
        logger.end()


