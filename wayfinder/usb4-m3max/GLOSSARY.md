# USB4 / Thunderbolt on the M3 Max

The language for bringing USB4 and Thunderbolt up on the 16" MacBook Pro M3 Max, so that every ticket on the map names the same hardware and the same goals the same way.

## Machine

**J516M**:
The 16-inch MacBook Pro with the 14-core-CPU, 30-core-GPU M3 Max (T6034) that this effort targets.
_Avoid_: M3 Max MacBook (ambiguous with J514M/J516C), Mac15,11

**T6034**:
The M3 Max SoC in the J516M; its Linux device tree builds on the T6031 one.
_Avoid_: M3 Max (when the SoC itself is meant)

**Sibling board**:
A Mac whose USB4 already works in the tree and that the spec borrows from: the J516S/J514S (M3 Pro, T6030) and the M2 Max (T6021).
_Avoid_: reference board

## USB4 hardware

**Port**:
One of the J516M's three USB-C/Thunderbolt sockets, each with its own ACIO, NHI and ATC PHY.
_Avoid_: controller, lane

**ACIO**:
Apple's per-port USB4 controller block (`cio@…` in the device tree) that holds the NHI and the tunnel root port.
_Avoid_: CIO controller, USB4 controller

**NHI**:
The native host interface of a port: the part the Linux Thunderbolt core talks to, whose binding creates the port's host router and USB4 domain.
_Avoid_: Thunderbolt host, TB controller

**ATC PHY**:
The per-port Type-C PHY that switches the socket between USB2/3, DisplayPort and USB4 modes.
_Avoid_: atcphy, Type-C PHY

**Tunnel root port**:
The PCIe root port behind an ACIO through which PCIe tunnels reach devices.
_Avoid_: PCIe-C, usb4 rc

## Capabilities

**Tunnel**:
A protocol carried over a USB4 link: a PCIe tunnel, a DisplayPort tunnel or a USB3 tunnel.
_Avoid_: path (a Thunderbolt-core term for a hop inside a tunnel)

**Bring-up**:
The state where a port's NHI binds and its USB4 domain and host router appear, before any tunnel exists.
_Avoid_: enablement, probe

**Baseline**:
The behaviour and throughput macOS shows on the same J516M, port and device, which Linux acceptance is measured against.
_Avoid_: reference numbers

**eGPU compute**:
An AMD GPU in a USB4 enclosure used for Vulkan or ROCm compute, with no display output.
_Avoid_: eGPU (alone), external graphics
