import argparse
import os
from dataclasses import dataclass

import litex.soc.integration.export as export
import litex.soc.interconnect.csr_bus as csr_bus
from litex.build.generic_platform import Pins, Subsignal
from litex.build.io import CRG as SimCRG
from litex.soc.cores import timer, uart
from litex.soc.cores.cpu.vexriscv import VexRiscv
from litex.soc.integration.soc import SoCCSRRegion, SoCRegion
from litex.soc.interconnect.axi import (
    AXI2AXILite,
    AXIInterconnectShared,
    AXIInterface,
    AXILite2CSR,
    AXILiteInterface,
    AXILiteSRAM,
    Wishbone2AXI,
)
from litex_boards.platforms.antmicro_lpddr4_test_board import Platform
from litex_boards.targets import antmicro_lpddr4_test_board
from migen import *

sim_serial = [
    (
        "sim_serial",
        0,
        Subsignal("source_valid", Pins(1)),
        Subsignal("source_ready", Pins(1)),
        Subsignal("source_data", Pins(8)),
        Subsignal("sink_valid", Pins(1)),
        Subsignal("sink_ready", Pins(1)),
        Subsignal("sink_data", Pins(8)),
    )
]


@dataclass
class SoCBusHandlerMock:
    address_width: int
    data_width: int
    bursting: bool = False


class SoC(Module):
    def __init__(
        self,
        platform,
        sim,
        uart_type,
        build_dir,
        sys_clk_freq=50e6,
        iodelay_clk_freq=400e6,
    ):
        bus_mock = SoCBusHandlerMock(address_width=32, data_width=32)
        self.slaves = []
        self.masters = []
        self.ios = set()
        self.mem_regions = {}
        self.csr_addr_map = {
            "uart": 0x0,
            "timer0": 0x1,
        }
        self.csr_paging = 0x200

        self.sim = sim
        self.uart_type = uart_type
        self.build_dir = build_dir

        self.submodules.core = VexRiscv(platform, variant="linux")
        self.core.set_reset_address(self.core.mem_map["rom"])
        self.submodules.timer0 = timer.Timer()

        if self.sim:
            self.submodules.crg = SimCRG(platform.request("clk100"))
        else:
            self.submodules.crg = antmicro_lpddr4_test_board._CRG(
                platform, sys_clk_freq, iodelay_clk_freq
            )

        if self.sim:
            platform.add_extension(sim_serial)
            self.uart_pads = platform.request("sim_serial")
            self.submodules.uart_phy = uart.RS232PHYModel(self.uart_pads)
        else:
            self.uart_pads = platform.request("serial", number=1)
            self.submodules.uart_phy = uart.UARTPHY(
                self.uart_pads, sys_clk_freq, 115200
            )
        self.ios.update(self.uart_pads.flatten())

        if self.uart_type == "uartbone":
            self.submodules.uart = uart.UARTBone(phy=self.uart_phy, clk_freq=1e6)
            # UARTBone expects exactly 32-bit address width while the CPU has 30-bit address width
            # There are also 2 bits added to each on the AXI side when converting from wishbone to AXI
            # so the final address width here has to be 34 bits
            iface = AXIInterface(address_width=34, name="axiinterface_uart")
            self.masters.append(iface)
            self.submodules += Wishbone2AXI(self.uart.wishbone, iface)
        elif self.uart_type == "uart":
            self.submodules.uart = uart.UART(phy=self.uart_phy)

        csr_master = csr_bus.Interface()
        self.submodules.csrs = csrs = csr_bus.CSRBankArray(
            self, lambda name, _: self.csr_addr_map[name], paging=self.csr_paging
        )
        if csrs.get_buses():
            self.submodules += csr_bus.Interconnect(
                master=csr_master, slaves=csrs.get_buses()
            )

        csr_axilite = AXILiteInterface(
            data_width=bus_mock.data_width,
            address_width=bus_mock.address_width,
            bursting=bus_mock.bursting,
            name="axiliteinterface_csr",
        )
        csr_axi = AXIInterface(
            data_width=bus_mock.data_width,
            address_width=bus_mock.address_width,
            id_width=1,
            name="axiinterface_csr",
        )
        self.submodules += AXILite2CSR(axi_lite=csr_axilite, bus_csr=csr_master)
        self.submodules += AXI2AXILite(csr_axi, csr_axilite)

        csr_region = SoCRegion(origin=self.core.mem_map["csr"], size=0x1000)
        self.slaves.append((csr_region.decoder(bus_mock), csr_axi))

        for bus in self.core.periph_buses:
            iface = AXIInterface(name="axiinterface_cpubus")
            self.masters.append(iface)
            self.submodules += Wishbone2AXI(bus, iface)

        self.add_memory(
            bus_mock, self.core.mem_map["rom"], 0xA000, read_only=True, name="rom"
        )
        self.add_memory(bus_mock, self.core.mem_map["sram"], 0x1000, name="sram")

    def gen_csr_header(self):
        header = ""
        csr_regions = {}
        for csr_group, csr_list, _, _ in self.csrs.banks:
            offset = self.csr_addr_map[csr_group] * self.csr_paging
            csr_regions[csr_group] = SoCCSRRegion(
                origin=self.core.mem_map["csr"] + offset, busword=32, obj=csr_list
            )
        if csr_regions:
            header += export.get_csr_header(csr_regions, {}, self.core.mem_map["csr"])
            header += "#define UART_POLLING\n"
        return header

    def gen_soc_header(self):
        header = ""
        header += "#define CONFIG_CSR_DATA_WIDTH 32\n"
        header += '#define CONFIG_CPU_NOP "nop"\n'
        header += "#define CONFIG_CLOCK_FREQUENCY 1000000\n"
        if self.sim:
            header += "#define CONFIG_BIOS_NO_DELAYS\n"
        return header

    def gen_mem_header(self):
        header = ""
        if self.mem_regions:
            header += export.get_mem_header(self.mem_regions)
        return header

    def write_headers(self):
        header_path = f"{self.build_dir}/generated"
        to_generate = {
            f"{header_path}/csr.h": self.gen_csr_header,
            f"{header_path}/soc.h": self.gen_soc_header,
            f"{header_path}/mem.h": self.gen_mem_header,
        }

        try:
            os.makedirs(header_path)
        except FileExistsError:
            if not os.path.isdir(header_path):
                raise

        for path, gen_f in to_generate.items():
            with open(path, "w") as file:
                file.write(gen_f())

    def add_memory(self, bus_mock, origin, size, read_only=False, init=[], name=None):
        bus_axilite = AXILiteInterface(
            data_width=bus_mock.data_width,
            address_width=bus_mock.address_width,
            bursting=bus_mock.bursting,
            name="axiliteinterface_" + name if name is not None else "",
        )
        bus_axi = AXIInterface(
            data_width=bus_mock.data_width,
            address_width=bus_mock.address_width,
            id_width=1,
            name="axiinterface_" + name if name is not None else "",
        )
        self.submodules += AXI2AXILite(bus_axi, bus_axilite)
        self.submodules += AXILiteSRAM(
            size, bus=bus_axilite, read_only=read_only, init=init, name=name
        )
        mem_region = SoCRegion(origin=origin, size=size)
        self.slaves.append((mem_region.decoder(bus_mock), bus_axi))

    def do_finalize(self):
        self.submodules += AXIInterconnectShared(
            masters=self.masters, slaves=self.slaves
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="SoC generator")
    parser.add_argument(
        "--uart-type",
        choices=["uartbone", "uart"],
        default="uartbone",
        help="Select generated UART interface",
    )
    parser.add_argument(
        "--verilog", action="store_true", help="Generate verilog sources"
    )
    parser.add_argument(
        "--headers",
        action="store_true",
        help="Generate headers required for compiling firmware",
    )
    parser.add_argument(
        "--build-dir",
        action="store",
        default="build/",
        help="Directory to write build files to",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--bitstream",
        action="store_true",
        help="Generate verilog sources and bitstream (invokes vivado)",
    )
    group.add_argument(
        "--sim",
        action="store_true",
        help="Generate build files appropriate for use in a verilator \
            simulation (controls behavior of other generation options)",
    )

    args = parser.parse_args()

    platform = Platform(device="xc7k70tfbg484-3")
    soc = SoC(platform, args.sim, args.uart_type, args.build_dir)
    if args.verilog:
        platform.get_verilog(soc).write(f"{args.build_dir}/top.v")
    if args.bitstream:
        platform.build(soc, run=False)
    if args.headers:
        soc.write_headers()
