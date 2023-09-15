from typing import Iterable

from amaranth import *
from amaranth.back import verilog
from amaranth.lib.wiring import *
from amaranth.utils import log2_int
from amaranth_soc import wishbone
from amaranth_soc.memory import MemoryMap


class DummyResource:
    pass


class WishboneRRInterconnect(Elaboratable):
    """Wishbone round-robin interconnect

    Generates a wishbone interconnect performing round-robin arbitration and peripheral address
    decoding. Exposes a signature and an interface containing all the endpoints for connecting
    masters and peripherals of requested size and address.

    Parameters
    ----------
    addr_width: int
        Address width of the address line
    data_width: int
        Data width of the data lines
    granularity: int
        Data access granularity - smallest unit of data transfer that the interconnect is capable
        of transferring. Must be one of: 8, 16, 32, 64
    features: Iterable[str]
        Iterable of optional wishbone features (signals) as strings, see
        ``amaranth_soc.wishbone.bus.Feature`` for a list of available features

    Attributes
    ----------
    signature: Signature
        Signature with wishbone sub-signatures corresponding to added masters and peripherals
    <interface_name>: Interface
        Interface with wishbone signals dynamically created by adding a master or a slave with
        ``add_master`` or ``add_slave`` respectively, with name specified as ``interface_name``
    """

    def __init__(
        self,
        *,
        addr_width: int,
        data_width: int,
        granularity: int,
        features: Iterable[str] = ()
    ):
        self.addr_width = addr_width
        self.data_width = data_width
        self.granularity = granularity
        self.features = features

        self.signature = Signature({})

        self._arbiter = wishbone.Arbiter(
            addr_width=self.addr_width,
            data_width=self.data_width,
            granularity=self.granularity,
            features=self.features,
        )
        self._decoder = wishbone.Decoder(
            addr_width=self.addr_width,
            data_width=self.data_width,
            granularity=self.granularity,
            features=self.features,
        )

    def elaborate(self, platform):
        m = Module()

        m.submodules.arbiter = self._arbiter
        m.submodules.decoder = self._decoder

        connect(m, self._arbiter.bus, self._decoder.bus)

        return m

    def add_master(self, *, name: str):
        # Amaranth convention is to describe signatures from the perspective of master, but from
        # the perspective of the interconnect the signature has to be flipped to be compatible with an actual master
        signature = wishbone.Signature(
            addr_width=self.addr_width,
            data_width=self.data_width,
            granularity=self.granularity,
            features=self.features,
        ).flip()
        bus = signature.create(path=(name,))
        setattr(self, name, bus)

        self.signature.members[name] = Out(signature)
        self._arbiter.add(flipped(bus))

    def add_peripheral(self, *, name: str, addr: int, size: int):
        addr_width = log2_int(size, need_pow2=False)
        granularity_bits = log2_int(self.data_width // self.granularity)

        # Convention of what addr_width and data_width mean for MemoryMap is different than for interfaces, in particular:
        # - addr_width is the "effective" address width - address width of the interface itself + granularity bits
        #   (used for selecting subword in a word, e.g. byte in a 32b word)
        # - data_width is width of the minimum addressable unit, e.g. a byte
        # This is mentioned in amaranth_soc.wishbone.Interface docstring
        mmap = MemoryMap(
            addr_width=addr_width + granularity_bits,
            data_width=self.granularity,
            alignment=log2_int(self.data_width),
        )
        mmap.add_resource(DummyResource(), name=name, size=size)

        signature = wishbone.Signature(
            addr_width=addr_width,
            data_width=self.data_width,
            granularity=self.granularity,
            features=self.features,
        )
        signature.memory_map = mmap
        bus = signature.create(path=(name,))
        setattr(self, name, bus)

        self.signature.members[name] = Out(signature)
        self._decoder.add(bus, addr=addr)
