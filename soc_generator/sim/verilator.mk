# Copyright 2023 Antmicro
# SPDX-License-Identifier: Apache-2.0

VERILATOR = verilator

VEXRISCV_DIR = $(shell python -c "import pythondata_cpu_vexriscv as cpu; print(cpu.__path__[0])")
VERILOG_SRC = $(BUILD_DIR)/top_sim.v $(BUILD_DIR)/wishbone_interconnect.v $(VEXRISCV_DIR)/verilog/VexRiscv_Linux.v
CPP_SRC = ../$(SIM_DIR)/sim.cpp ../$(SIM_DIR)/sim_uart.cpp

VERILATOR_FLAGS += -cc --exe -x-assign fast -Wall --trace --assert --coverage -Wno-fatal --build --build-jobs 0 --top-module top --Mdir $(BUILD_DIR)/obj_dir
VERILATOR_INPUT = $(VERILOG_SRC) $(CPP_SRC)

$(BUILD_DIR)/obj_dir/Vtop: $(VERILOG_SRC)
	$(VERILATOR) $(VERILATOR_FLAGS) $(VERILATOR_INPUT)
