# Tools
PYTHON = python3
PREFIX = riscv64-unknown-elf
CC = $(PREFIX)-gcc
OBJCOPY = $(PREFIX)-objcopy
NINJA = ninja
MESON = meson

# Files
HEADERS = csr.h soc.h mem.h
PY_SRC = generate_soc.py amaranth_wrapper.py wishbone_interconnect.py
BUILD_DIR ?= build

BASE_SOC_OPTS = --uart-type uart --build-dir $(BUILD_DIR)
TARGET_SOC_OPTS =

all: picolibc sim synth

include headers.mk
include bios.mk
include verilator.mk

deps: picolibc

upload: $(BUILD_DIR)/top.bit
	openFPGALoader --board antmicro_lpddr4_tester $<

sim: TARGET_SOC_OPTS += --sim --verilog
sim: $(BUILD_DIR)/obj_dir/Vtop

synth: $(BUILD_DIR)/top.bit

sim-run: sim firmware
	cd $(BUILD_DIR) && obj_dir/Vtop +trace
	sed -i 's/.cc:2083:/_/g' $(BUILD_DIR)/dump.vcd

picolibc:
	mkdir -p $(PICOLIBC)/build
	cd $(PICOLIBC)/build && ../scripts/do-riscv-configure \
		-Dmultilib-list=rv32im/ilp32 \
		-Dprefix=$(CURDIR)/$(PICOLIBC)/install \
		-Dspecsdir=$(CURDIR)/$(PICOLIBC)/install
	$(NINJA) -C $(PICOLIBC)/build
	$(MESON) install -C $(PICOLIBC)/build --only-changed

$(BUILD_DIR)/top.v: $(PY_SRC) | $(BUILD_DIR)
	$(PYTHON) generate_soc.py $(BASE_SOC_OPTS) $(TARGET_SOC_OPTS)
	rm -f *.init
	touch $@

$(BUILD_DIR)/top.tcl: $(PY_SRC) | $(BUILD_DIR)
	$(PYTHON) generate_soc.py --bitstream $(BASE_SOC_OPTS) $(TARGET_SOC_OPTS)
	rm -f *.init
	touch $@

$(AUTOGEN_H) &: $(PY_SRC) | $(BUILD_DIR)
	$(PYTHON) generate_soc.py --headers $(BASE_SOC_OPTS)

$(BUILD_DIR)/top.bit: $(BUILD_DIR)/top.v $(BUILD_DIR)/top.tcl $(BUILD_DIR)/top_rom.init | $(BUILD_DIR)
	cd build && vivado -mode batch -source top.tcl

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

clean:
	rm -rf $(BUILD_DIR)

distclean: clean
	rm -rf $(PICOLIBC)/build $(PICOLIBC)/install

.PHONY: all deps upload sim sim-run synth picolibc clean distclean
