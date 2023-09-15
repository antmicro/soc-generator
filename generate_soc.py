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
from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import AutoCSR, CSRStatus, CSRStorage
from litex_boards.platforms.antmicro_lpddr4_test_board import Platform
from litex_boards.targets import antmicro_lpddr4_test_board
from migen import *

from amaranth_wrapper import Amaranth2Migen
from wishbone_interconnect import WishboneRRInterconnect

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
        self.slaves = {}
        self.masters = {}
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
            self.masters["uartbone"] = self.uart.wishbone
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

        csr_wishbone = wishbone.Interface(
            data_width=bus_mock.data_width,
            adr_width=bus_mock.data_width,
            bursting=bus_mock.bursting,
        )
        self.submodules += wishbone.Wishbone2CSR(
            bus_wishbone=csr_wishbone, bus_csr=csr_master
        )

        csr_region = SoCRegion(origin=self.core.mem_map["csr"], size=0x1000)
        self.slaves["csr"] = (csr_wishbone, csr_region)

        self.masters["cpu_ibus"] = self.core.ibus
        self.masters["cpu_dbus"] = self.core.dbus

        self.add_memory(
            bus_mock, self.core.mem_map["rom"], 0xA000, read_only=True, name="rom"
        )
        self.add_memory(bus_mock, self.core.mem_map["sram"], 0x1000, name="sram")

        self.create_interconnect(self.masters, self.slaves)

    def create_interconnect(self, masters, slaves):
        ic = WishboneRRInterconnect(
            addr_width=30, data_width=32, granularity=8, features={"bte", "cti", "err"}
        )

        for name, _ in masters.items():
            ic.add_master(name=name)
        for name, (_, mem_region) in slaves.items():
            ic.add_peripheral(name=name, addr=mem_region.origin, size=mem_region.size)

        self.submodules.interconnect = Amaranth2Migen(
            ic, platform, "wishbone_interconnect", self.build_dir
        )

        for name, master in masters.items():
            self.comb += master.connect(self.interconnect.interfaces[name])

        for name, (slave, _) in slaves.items():
            self.comb += self.interconnect.interfaces[name].connect(slave)

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
        bus = wishbone.Interface()
        self.submodules += wishbone.SRAM(
            size, bus=bus, read_only=read_only, init=init, name=name
        )
        mem_region = SoCRegion(origin=origin, size=size)
        self.slaves[name] = (bus, mem_region)


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
        # Workaround - because litex does os.chdir in platform.build(), we also have to change
        # the working directory to be consistent (this is important for internal modules of
        # the SoC that might also generate verilog)
        os.chdir(args.build_dir)
        platform.get_verilog(soc).write(f"top.v")
    if args.bitstream:
        platform.build(soc, build_dir=args.build_dir, build_name="top", run=False)
    if args.headers:
        soc.write_headers()
