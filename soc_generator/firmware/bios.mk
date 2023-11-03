# Copyright 2023 Antmicro
# SPDX-License-Identifier: Apache-2.0

include $(FIRMWARE_DIR)/headers.mk

LITEX = $(shell python -c "import litex; print(litex.__path__[0])")/soc
PICOLIBC = third_party/picolibc

LIBBASE_OBJ = uart.o memtest.o system.o
FIRMWARE_OBJ = bios.o uart_stdio.o
LINKER_SCRIPT = $(FIRMWARE_DIR)/linker.ld

OBJ = $(addprefix $(FIRMWARE_DIR)/,$(FIRMWARE_OBJ)) $(addprefix $(LITEX)/software/libbase/,$(LIBBASE_OBJ))
INC = $(BUILD_DIR) $(LITEX)/software/include $(LITEX)/software/libbase $(LITEX)/software $(LITEX)/cores/cpu/vexriscv
CFLAGS = -march=rv32im -mabi=ilp32 --specs=$(PICOLIBC)/install/picolibc.specs -T$(LINKER_SCRIPT) $(addprefix -I,$(INC))
BIN = $(BUILD_DIR)/rom.bin
OBJ_BUILD = $(addprefix $(BUILD_DIR)/,$(OBJ))
DIRTREE = $(sort $(dir $(OBJ_BUILD)))

firmware: $(BUILD_DIR)/bios.init

$(BUILD_DIR)/%.o: %.c $(AUTOGEN_H) | $(DIRTREE)
	$(CC) $(CFLAGS) -c -o $@ $<

$(BUILD_DIR)/bios.bin: $(OBJ_BUILD)
	$(CC) $(CFLAGS) -o $@ $(OBJ_BUILD)

$(BUILD_DIR)/rom.bin: $(BUILD_DIR)/bios.bin
	$(OBJCOPY) -O binary $^ $@

$(BUILD_DIR)/%.init: $(BIN) | $(BUILD_DIR)
	hexdump -v -e '1/4 "%08X\n"' $< > $@

$(DIRTREE):
	mkdir -p $@

.PHONY: firmware
