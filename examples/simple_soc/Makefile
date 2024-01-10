# Copyright 2023 Antmicro
# SPDX-License-Identifier: Apache-2.0

# Tools
PYTHON = python3
PREFIX = riscv64-unknown-elf
CC = $(PREFIX)-gcc
OBJCOPY = $(PREFIX)-objcopy
NINJA = ninja
MESON = meson

# Directories
FIRMWARE_DIR = firmware
GEN_DIR = ../../soc_generator/gen
SCRIPTS_DIR = scripts
SIM_DIR = sim

# Files
PY_SRC = $(SCRIPTS_DIR)/generate_soc.py $(GEN_DIR)/amaranth_wrapper.py $(GEN_DIR)/wishbone_interconnect.py
SOC_GEN = python $(SCRIPTS_DIR)/generate_soc.py
BUILD_DIR ?= build

BASE_SOC_OPTS = --uart-type uart --build-dir $(BUILD_DIR)
TARGET_SOC_OPTS =

all: picolibc sim bitstream

include $(FIRMWARE_DIR)/headers.mk
include $(FIRMWARE_DIR)/bios.mk
include $(SIM_DIR)/verilator.mk

deps: picolibc

upload: $(BUILD_DIR)/top.bit
	openFPGALoader --board antmicro_lpddr4_tester $<

sim: TARGET_SOC_OPTS += --sim --verilog --build-name top_sim
sim: $(BUILD_DIR)/obj_dir/Vtop

rtl: TARGET_SOC_OPTS += --build-name top
rtl: $(BUILD_DIR)/top.v

bitstream: $(BUILD_DIR)/top.bit

sim-run: sim firmware
	cd $(BUILD_DIR) && obj_dir/Vtop +trace
	sed -i 's/.cc:[[:digit:]]\+:/_/g' $(BUILD_DIR)/dump.vcd

picolibc:
	mkdir -p $(PICOLIBC)/build
	cd $(PICOLIBC)/build && ../scripts/do-riscv-configure \
		-Dmultilib-list=rv32im/ilp32 \
		-Dprefix=$(CURDIR)/$(PICOLIBC)/install \
		-Dspecsdir=$(CURDIR)/$(PICOLIBC)/install
	$(NINJA) -C $(PICOLIBC)/build
	$(MESON) install -C $(PICOLIBC)/build --only-changed

$(BUILD_DIR)/top_sim.v: $(PY_SRC) | $(BUILD_DIR)
	$(SOC_GEN) $(BASE_SOC_OPTS) $(TARGET_SOC_OPTS)
	sed -i 's/"top_rom.init"/"bios.init"/g' $(BUILD_DIR)/top_sim.v

$(BUILD_DIR)/top.tcl $(BUILD_DIR)/top.v &: $(PY_SRC) | $(BUILD_DIR)
	$(SOC_GEN) --bitstream $(BASE_SOC_OPTS) $(TARGET_SOC_OPTS)
	sed -i 's/"top_rom.init"/"bios.init"/g' $(BUILD_DIR)/top.v

$(AUTOGEN_H) &: $(PY_SRC) | $(BUILD_DIR)
	$(SOC_GEN) --headers $(BASE_SOC_OPTS)

$(BUILD_DIR)/top.bit: $(BUILD_DIR)/top.v $(BUILD_DIR)/top.tcl $(BUILD_DIR)/bios.init | $(BUILD_DIR)
	cd $(BUILD_DIR) && vivado -mode batch -source top.tcl

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

clean:
	rm -rf $(BUILD_DIR)

distclean: clean
	rm -rf $(PICOLIBC)/build $(PICOLIBC)/install

.PHONY: all deps upload sim sim-run rtl bitstream picolibc clean distclean
