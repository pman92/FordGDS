// Copyright (c) 2025 MR MODULE PTY LTD
// Licensed under the MIT License

#include "header.h"

void processSerialCommands() {
    static uint8_t buffer[40];
    static uint8_t index = 0;
    static uint8_t expected_len = 0;
    static unsigned long last_byte_time = 0;

    while (Serial.available()) {
        unsigned long now = millis();
        if (now - last_byte_time > 100) {
            index = 0;
            expected_len = 0;
        }
        last_byte_time = now;

        uint8_t b = Serial.read();
    
        if (index == 0) expected_len = 0;
    
        buffer[index++] = b;
    
        if (index == 2) {
            expected_len = buffer[1];
            if (expected_len < 3 || expected_len > sizeof(buffer)) {
                index = 0;  // invalid length
            }
        }
    
        if (index >= expected_len && expected_len > 0) {
            uint8_t checksum = 0;
            for (uint8_t i = 0; i < expected_len - 1; i++) checksum += buffer[i];
    
            if (checksum != buffer[expected_len - 1]) {
                index = 0;
                return; // bad checksum
            }
    
            uint8_t cmd  = buffer[0];
            uint8_t addr = buffer[2];
    
            // === READ 1 BYTE ===
            if (cmd == 0x10 && expected_len == 4) {
                uint8_t val = eeprom_data[addr];
                Serial.write((uint8_t)0x10);
                Serial.write((uint8_t)0x05);
                Serial.write(addr);
                Serial.write(val);
                Serial.write((uint8_t)(0x10 + 0x05 + addr + val)); // Checksum
            }
    
            // === READ 32 BYTES ===
            else if (cmd == 0x11 && expected_len == 4) {
                Serial.write((uint8_t)0x11);
                Serial.write((uint8_t)0x24);
                Serial.write(addr);
                uint8_t sum = 0x11 + 0x24 + addr;
                for (uint8_t i = 0; i < 32; i++) {
                    uint8_t val = eeprom_data[(uint8_t)(addr + i)];
                    Serial.write(val);
                    sum += val;
                }
                Serial.write(sum);
            }
    
            // === WRITE 1 BYTE ===
            else if (cmd == 0x20 && expected_len == 5) {
                uint8_t val = buffer[3];
                eeprom_data[addr] = val;
                Serial.write((uint8_t)0x20);
                Serial.write((uint8_t)0x05);
                Serial.write(addr);
                Serial.write((uint8_t)0x00);  // ACK
                Serial.write((uint8_t)(0x20 + 0x05 + addr));
            }
    
            // === WRITE 32 BYTES ===
            else if (cmd == 0x21 && expected_len == 36) {
                for (uint8_t i = 0; i < 32; i++) {
                    eeprom_data[(uint8_t)(addr + i)] = buffer[3 + i];
                }
                Serial.write((uint8_t)0x21);
                Serial.write((uint8_t)0x05);
                Serial.write(addr);
                Serial.write((uint8_t)0x00);  // ACK
                Serial.write((uint8_t)(0x21 + 0x05 + addr));
            }

            // === ACCESSED BYTES MAP ===
            else if (cmd == 0x30 && expected_len == 3) {
                Serial.write((uint8_t)0x30);
                Serial.write((uint8_t)0x23);
                uint8_t sum = 0x30 + 0x24;
                for (uint8_t i = 0; i < 32; i++) {
                    Serial.write(accessed_flags[i]);
                    sum += accessed_flags[i];
                }
                Serial.write(sum);
            }
            
            // === MODIFIED BYTES MAP ===
            else if (cmd == 0x31 && expected_len == 3) {
                Serial.write((uint8_t)0x31);
                Serial.write((uint8_t)0x23);
                uint8_t sum = 0x31 + 0x24;
                for (uint8_t i = 0; i < 32; i++) {
                    Serial.write(modified_flags[i]);
                    sum += modified_flags[i];
                }
                Serial.write(sum);
            }

            // === SAVE TO INTERNAL EEPROM ===
            else if (cmd == 0x40 && expected_len == 3) {
                for (uint16_t i = 0; i < 256; i++) {
                    EEPROM.update(i, eeprom_data[i]);
                }
                EEPROM.update(EEPROM_DATA_VALID_FLAG, EEPROM_FLAG_VALUE);
                Serial.write((uint8_t)0x40);
                Serial.write((uint8_t)0x03);
                Serial.write((uint8_t)(0x40 + 0x03));
            }

            // === LOAD FROM INTERNAL EEPROM ===
            else if (cmd == 0x41 && expected_len == 3) {
                for (uint16_t i = 0; i < 256; i++) {
                    eeprom_data[i] = EEPROM.read(i);
                }
                Serial.write((uint8_t)0x41);
                Serial.write((uint8_t)0x03);
                Serial.write((uint8_t)(0x41 + 0x03));
            }

            // === SAVE FLAGS TO INTERNAL EEPROM ===
            else if (cmd == 0x42 && expected_len == 3) {
                for (uint16_t i = 0; i < 32; i++) {
                    EEPROM.update(256 + i, accessed_flags[i]);
                    EEPROM.update(288 + i, modified_flags[i]);
                }
                EEPROM.update(EEPROM_ACCESSED_VALID_FLAG, EEPROM_FLAG_VALUE);
                EEPROM.update(EEPROM_MODIFIED_VALID_FLAG, EEPROM_FLAG_VALUE);
                Serial.write((uint8_t)0x42);
                Serial.write((uint8_t)0x03);
                Serial.write((uint8_t)(0x42 + 0x03));
            }

            // === LOAD FLAGS FROM INTERNAL EEPROM ===
            else if (cmd == 0x43 && expected_len == 3) {
                for (uint16_t i = 0; i < 32; i++) {
                    accessed_flags[i] = EEPROM.read(256 + i);
                    modified_flags[i] = EEPROM.read(288 + i);
                }
                Serial.write((uint8_t)0x43);
                Serial.write((uint8_t)0x03);
                Serial.write((uint8_t)(0x43 + 0x03));
            }

            // === RESET COMMAND (0xA0) ===
            else if (cmd == 0xA0 && expected_len == 3) {
                resetEepromState();
                Serial.write((uint8_t)0xA0);
                Serial.write((uint8_t)0x03);
                Serial.write((uint8_t)(0xA0 + 0x03));
            }

            // === CLEAR FLAGS ONLY (0xA1) ===
            else if (cmd == 0xA1 && expected_len == 3) {
                memset(accessed_flags, 0, 32);
                memset(modified_flags, 0, 32);
                Serial.write((uint8_t)0xA1);
                Serial.write((uint8_t)0x03);
                Serial.write((uint8_t)(0xA1 + 0x03));
            }
    
            index = 0;
        }
    }
  }
