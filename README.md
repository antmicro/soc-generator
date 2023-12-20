# SoC generator
This is a collection of tools for comprehensively generating SoCs together with their firmware.

## Install prerequisites
You need to install:
- python 3.9 (specifically this version due to litex compatibility issues with other versions) and pip
- riscv64-unknown-elf and native toolchain
- make
- meson
- ninja
- hexdump (contained in package bsdextrautils)

```
sudo apt install git make g++ ninja-build gcc-riscv64-unknown-elf bsdextrautils
```

For installing and managing python dependencies using `conda` is recommended:
```
conda create -n venv python=3.9
conda activate venv
pip install -r requirements.txt
```

To run the simulation you also need:
- verilator

To create and load bitstream you also need:
- vivado (preferably version 2020.2)
- openFPGALoader ([this branch](https://github.com/antmicro/openFPGALoader.git))

## Usage

Before building the project itself you need to set up your environment and build dependencies:
```
source ./env
make deps
```

## Running simulation

To build the simulation and run hello world example run:
```
make sim-run
```

## Synthesis

To build the bitstream and upload it to the FPGA board run:
```
make synth
make upload
```

