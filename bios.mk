include headers.mk

LITEX = third_party/litex/litex/soc
PICOLIBC = third_party/picolibc

LIBBASE_OBJ = uart.o memtest.o system.o

OBJ = bios.o uart_stdio.o $(addprefix $(LITEX)/software/libbase/,$(LIBBASE_OBJ))
INC = $(BUILD_DIR) $(LITEX)/software/include $(LITEX)/software/libbase $(LITEX)/software $(LITEX)/cores/cpu/vexriscv
CFLAGS = -march=rv32im -mabi=ilp32 --specs=$(PICOLIBC)/install/picolibc.specs -Tlinker.ld $(addprefix -I,$(INC))
BIN = $(BUILD_DIR)/rom.bin
OBJ_BUILD = $(addprefix $(BUILD_DIR)/,$(OBJ))
DIRTREE = $(sort $(dir $(OBJ_BUILD)))

firmware: $(BUILD_DIR)/top_rom.init

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
