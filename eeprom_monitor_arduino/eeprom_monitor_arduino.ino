// Copyright (c) 2025 MR MODULE PTY LTD
// Licensed under the MIT License

/*  Arduino sketch for use with eeprom_monitor.py Python script
 *  Currently setup for 24C02 I2C EEPROM on Arduino Uno
 *  Remove physical EEPROM and connect I2C pins (A4 / A5) and ground from Arduino in its place (assuming eeprom is 5v logic)
 */

#include "header.h"

volatile uint8_t mem_address = 0;    // EEPROM memory pointer
const uint8_t default_eeprom_data[256] = EEPROM_DATA
volatile uint8_t eeprom_data[256] = {0};

uint8_t accessed_flags[32] = {0}; // Set if EEPROM address was read via I2C
uint8_t modified_flags[32] = {0}; // Set if EEPROM address was written via I2C

bool address_received = false;  // Tracks whether we've received an address byte

// Called when master writes data (e.g. to set pointer or write values)
void receiveEvent(int howMany) {
  if (howMany < 1) return;

  // First byte is memory address
  mem_address = Wire.read();
  address_received = true;
  howMany--;

  // Remaining bytes are data to write
  while (howMany-- > 0) {
    uint8_t value = Wire.read();
    eeprom_data[mem_address] = value;
    modified_flags[mem_address / 8] |= (1 << (mem_address % 8));
    mem_address++;
  }
}

// Called when master reads data from us
void requestEvent() {
  uint8_t val = eeprom_data[mem_address];
  accessed_flags[mem_address / 8] |= (1 << (mem_address % 8));
  Wire.write(val);
  mem_address++;
}

void resetEepromState() {
  memcpy((void*)eeprom_data, default_eeprom_data, 256); //Clear eeprom
  memset(accessed_flags, 0, 32); //Clear flags
  memset(modified_flags, 0, 32);
}

void setup() {
  Wire.begin(EEPROM_I2C_ADDRESS);  // Start I2C in slave mode
  Wire.onReceive(receiveEvent);    // Handle master write
  Wire.onRequest(requestEvent);    // Handle master read

  resetEepromState();
  if (EEPROM.read(EEPROM_DATA_VALID_FLAG) == EEPROM_FLAG_VALUE) {
    for (uint16_t i = 0; i < 256; i++) eeprom_data[i] = EEPROM.read(i);
  }
  if (EEPROM.read(EEPROM_ACCESSED_VALID_FLAG) == EEPROM_FLAG_VALUE) {
    for (uint8_t i = 0; i < 32; i++) accessed_flags[i] = EEPROM.read(256 + i);
  }
  if (EEPROM.read(EEPROM_MODIFIED_VALID_FLAG) == EEPROM_FLAG_VALUE) {
    for (uint8_t i = 0; i < 32; i++) modified_flags[i] = EEPROM.read(288 + i);
  }
  

  Serial.begin(SERIAL_BAUD);
  // Send reset notification packet: [0x0A, 0x03, 0x0D]
  Serial.write((uint8_t)0x0A);  // start byte
  Serial.write((uint8_t)0x03);  // length
  Serial.write((uint8_t)(0x0A + 0x03));  // checksum
}

void loop() {
  processSerialCommands();
}
