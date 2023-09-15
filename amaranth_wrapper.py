from dataclasses import dataclass

from amaranth import Elaboratable, Shape
from amaranth.back import verilog
from amaranth.build.plat import Platform
from amaranth.lib import enum, wiring
from migen import *


@dataclass(frozen=True)
class SignatureRecord:
    signature: wiring.Signature
    record: Record


class Amaranth2Migen(Module):
    """Amaranth-to-Migen wrapper Module

    Converts an Amaranth ``Elaboratable`` to verilog and constructs a Migen ``Module`` with
    identical public interface. For each Amaranth's ``Interface`` a corresponding Migen ``Record``
    is created with the same fields and assigned as an object member field under the same name.
    Recursive interfaces are also supported.

    Amaranth has two concepts to describe interfaces exposed by a module:
    - ``amaranth.lib.wiring.Signature`` class - it contains a description of a bundle of wires,
      each with its own width and direction
    - ``amaranth.lib.wiring.Interface`` class - it contains a concrete instantiation of a ``Signature``,
      i.e. actual Amaranth ``Signal``s. Interfaces can be created from signatures.
    Convention is to use ``signature`` member in an ``Elaboratable`` to describe the public interface
    of a module. More details can be found here:
    https://github.com/amaranth-lang/rfcs/blob/main/text/0002-interfaces.md#guide-level-explanation

    Migen uses ``Record`` class to describe and instantiate a bundle of wires. It serves a similar
    function to Amaranth's ``Signature`` and ``Interface``.

    This class iterates all public interfaces of ``elaboratable`` and creates a Migen ``Record``
    corresponding to each of them. Those records are directly connected to corresponding ports in
    an instantiation of ``elaboratable`` dumped to verilog.

    Parameters
    ----------
    elaboratable: Elaboratable
        Amaranth elaboratable object
    platform: Platform
        Amaranth platform object
    name: str
        Name of this module. It's used as a name for the verilog module and generated verilog file
    build_dir: str
        Path to the build directory

    Attributes
    ----------
    interfaces: dict[str, Record]
        Mapping from Amaranth's names of interfaces of ``elaboratable`` to Migen records with
        identical structure
    """

    def __init__(
        self, elaboratable: Elaboratable, platform: Platform, name: str, build_dir: str
    ):
        self.elaboratable = elaboratable
        self.platform = platform
        self.name = name
        self.build_dir = build_dir
        self.interfaces = {}
        self._ports = {
            "i_clk": ClockSignal("sys"),
            "i_rst": ResetSignal("sys"),
        }
        self.clk = ClockSignal("sys")
        self.rst = ResetSignal("sys")

        self.create_interfaces()

    @staticmethod
    def signature2sigrec(signature: wiring.Signature) -> SignatureRecord:
        layout = []
        # flip signature if it's flipped so that ports in it have original flow directions
        # which are needed to correctly assign direction in record layout (DIR_M_TO_S or DIR_S_TO_M)
        if isinstance(signature, wiring.FlippedSignature):
            sig_unflipped = signature.flip()
        else:
            sig_unflipped = signature

        for port_name, port in sig_unflipped.members.items():
            if port.is_port:
                # Amaranth convention is to assign port flows from the point of master, hence
                # wiring.Out is equivalent to Migen's DIR_M_TO_S
                layout.append(
                    (
                        port_name,
                        Shape.cast(port.shape).width,
                        DIR_M_TO_S if port.flow == wiring.Out else DIR_S_TO_M,
                    )
                )
            else:  # port.is_signature
                layout.append((port_name, Amaranth2Migen.signature2sigrec(port)))
        return SignatureRecord(signature, Record(layout))

    @staticmethod
    def sigrec2signals(sig_rec: SignatureRecord, prefix_name: str) -> dict[str, Signal]:
        signals = {}
        for port_name, port in sig_rec.signature.members.items():
            rec_port = getattr(sig_rec.record, port_name)
            if port.is_port:
                name = f"{prefix_name}__{port_name}"
                signals[name] = (rec_port, port.flow)
            else:  # port.is_signature
                sig_rec = Amaranth2Migen.signature2sigrec(port)
                signals.update(Amaranth2Migen.signature2signals(sig_rec, port_name))
        return signals

    @staticmethod
    def sigrec2ports(sig_rec: SignatureRecord, prefix_name: str) -> dict[str, Signal]:
        signals = Amaranth2Migen.sigrec2signals(sig_rec, prefix_name)
        signals = {
            f"{'i' if flow == wiring.In else 'o'}_{name}": signal
            for name, (signal, flow) in signals.items()
        }
        return signals

    def create_interfaces(self):
        for name, signature_or_port in self.elaboratable.signature.members.items():
            if signature_or_port.is_signature:
                sig_rec = Amaranth2Migen.signature2sigrec(signature_or_port.signature)
                self.interfaces[name] = sig_rec.record
                setattr(self, name, sig_rec.record)

                ports = Amaranth2Migen.sigrec2ports(sig_rec, name)
                self._ports.update(ports)
            else:  # signature_or_port.is_port
                port = signature_or_port
                port_name = f"{'i' if port.flow == wiring.In else 'o'}_{name}"
                port_signal = Signal(port.shape)
                self.interfaces[name] = port_signal
                self._ports[port_name] = port_signal
                setattr(self, name, port_signal)

    def do_finalize(self):
        self.specials += Instance(self.name, **self._ports)

        with open(f"{self.name}.v", "w") as f:
            f.write(verilog.convert(self.elaboratable, name=self.name))
        self.platform.add_source(f"{self.name}.v")
