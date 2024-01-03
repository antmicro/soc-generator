# SoC generator

Copyright (c) 2023-2024 [Antmicro](https://www.antmicro.com)

This is a collection of tools for comprehensively generating SoCs together with their firmware.

## Install prerequisites
You need to install:
- python 3.9 or 3.10 (specifically one of those two versions due to litex compatibility issues with other versions) and pip
- riscv64-unknown-elf and native toolchain
- make
- meson
- ninja
- hexdump (contained in package bsdextrautils)

```
sudo apt install git make g++ ninja-build gcc-riscv64-unknown-elf bsdextrautils
```

To run the simulation you also need:
- verilator

To create and load bitstream you also need:
- vivado (preferably version 2020.2)
- openFPGALoader ([this branch](https://github.com/antmicro/openFPGALoader.git))

## Usage

Before building the project itself you need to install optional python dependencies and build third-party dependencies:
```
pip install ".[generate_soc_deps]"
make deps
```

## Running simulation

To build the simulation and run hello world example run:
```
make sim-run
```

## Bitstream generation

To build the bitstream and upload it to the FPGA board run:
```
make bitstream
make upload
```
