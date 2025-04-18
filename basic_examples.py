# Copyright (c) 2025 MR MODULE PTY LTD
# Licensed under the MIT License

import can, time
from GDS import FordGDS, GDSResult, GDSSession, logger

# Create CAN bus instance (adjust channel/interface if needed)
bus = can.Bus(interface='csscan_serial', channel='COM10', bitrate=500000)

# Create FordGDS instance
gds = FordGDS(bus)

# Create log file
logfile = open(logger.generate_log_filename(), "w")
logger.begin(logfile)

# We're going to test out some GDS functions with the PCM
gds.set_module('PCM')
time.sleep(0.1)

# Start a diagnostic session
result = gds.start_session(GDSSession.DIAGNOSTIC)
if(result == GDSResult.SUCCESS):
    logger.log("Diagnostic Session Started")
else:
    logger.log(f"Error Starting Diagnostic Session: {result}")

# Send a tester present message (this could/should be adapted to automatically keep transmitting)
gds.tester_present(True)
time.sleep(0.1)

# Read a DID
data = []
result = gds.read_data_by_identifier(0x0200, data)
if(result == GDSResult.SUCCESS):
    logger.log(f"DID 0x200 = {data}")
time.sleep(0.1)

# Read some memory (strategy name, at least for black oak)
first = []
result = gds.read_memory_by_address(0x10046, 6, first)
second = []
result = gds.read_memory_by_address(0x1004C, 5, second)
if(result == GDSResult.SUCCESS):
    logger.log(f"Memory = {bytes(first + second).decode('ascii', errors='replace')}")
time.sleep(0.1)

# Get security seed - we could also send key back with security_access_send_key()
seed = []
gds.security_access_request_seed(seed)
time.sleep(0.1)

# Reboot the PCM (won't be supported in a standard 0x81 diagnostic session)
gds.ecu_reset()
time.sleep(0.1)

# We can also send frames manually - the arbitration ID is defined by what you have set with gds.set_module()
frame = [0x03, 0x22, 0x02, 0x00] # same DID from before
gds.send(frame)

# And receive them manually 
returned_data = gds.receive() #optionally specify a timeout (defaults to 1 second)
logger.log(f"Returned data = {' '.join(f'{b:02X}' for b in returned_data)}")
if(returned_data[1] == 0x62):
    logger.log("Positive Response")
elif(returned_data[1] == 0x7F):
    logger.log("Negative Response")

# Send and receive long multi-frame (ISO-TP) messages is automatically supported, eg:
dtcs = gds.read_dtc_by_status()


# Finish up
gds.close()