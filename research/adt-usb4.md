# J516M: Apple device tree (ADT) against the Linux device tree for USB4

Research for #4 (part of #1). Question: where does the Linux device tree the
J516M boots disagree with Apple's own device tree for the USB4 hardware, port
by port?

## Sources

- **ADT**: `DeviceTree.j516map.im4p` from the macOS 26.2 (26B123) Mac15,11
  firmware, dumped with `ipsw dtree` to JSON. Also the J516C (T6031) ADT from
  the same firmware, for a T6031 vs T6034 diff. Reg addresses below are
  already translated through `/arm-io` `ranges` (the 0x7…/0xb…/0xf… windows map
  1:1; the 0x0 window maps to 0x2_0000_0000). Power-gate ids are resolved
  through the `/arm-io/pmgr` `devices` table; their register offsets and
  parents were recomputed from `ps-regs` and checked against
  `t6031-pmgr.dtsi`.
- **Linux DT**: branch `usb4-m3max` at `7369b2d68bbd`,
  `arch/arm64/boot/dts/apple/`: `t6034-j516m.dts` → `t6034.dtsi` →
  `t6031.dtsi` → `t6031-dieX.dtsi` / `t6031-pmgr.dtsi` / `t6031-die0.dtsi`,
  plus `t603x-j514-j516.dtsi`. All `file:line` below are relative to that
  directory unless they name another path.
- **Sibling path**: J516S `t6030-usb4.dtsi` and
  `t603x-j514s-j516s-usb4.dtsi`.
- **Live DT**: `/proc/device-tree` on the running J516M, to see which
  properties m1n1 fills at boot.
- **m1n1**: `m1n1-aurora` `src/kboot.c`, which names the ADT tunable
  properties that iBoot inserts and m1n1 copies.
- **Driver**: `drivers/thunderbolt/apple.c` on the same branch, only where a
  DT gap changes what the driver can do.

### What the ADT cannot show

The firmware ADT is the template that iBoot fills in at boot. It has **no**
iBoot-inserted tunables: no `top_tunables`, `hi_*_fabric_tunables`,
`pcie_adapter_regs_tunables`, `atc-apcie-*-tunables`, `tunable_ATC*`, and so
on (only placeholder `tunable-host`/`tunable-device` stubs on `atc-phy*`).
These blocks do exist in the live ADT: the running J516M's live DT has
`apple,tunable-rc` (360 B), `apple,tunable-nhi` (2712 B) and the ATC PHY
tunables, which m1n1 can only have copied from the live ADT. So this note
lists tunables by **name and destination**, from m1n1's tables. It does not
give values, and it cannot prove that a given block is present in the live ADT.

## Summary

1. **There is no tunnel root port on any port.** The ADT has `apciec0/1/2`
   (PCIe-C root ports, `compatible = "apciec,t8122"`) with their DARTs
   (`dart-apciec0/1/2`) and PIO-DMA engines (`apciec0/1/2-piodma`). The
   T6031/T6034 Linux DT has none of them. The J516S has only port 0's
   (`t6030-usb4.dtsi:40-129`).
2. **The ACIO nodes miss two ADT regions.** The `pcie-adapter` region
   (ADT `acioN` reg[5], 0xN01e44000) and the MxWrap `cpu` region (ADT
   `acio-cpuN` reg[1], 0xN01100000) are both absent. The ADT names the
   T6034 ACIO coprocessor `iop,mxwrap-acio`, the same wrapper the T6030 driver
   path drives through that `cpu` region. The driver's T6031 match data assumes
   there is no MxWrap (`drivers/thunderbolt/apple.c:154-160`).
3. **The ACIO power-domains miss `ATCn_PCIE`.** The ADT gives it to `apciecN`
   (`power-gates = <AUSBn-AONPCIE-V, ATCn_PCIE>`). Linux defines
   `ps_atcN_pcie` but nothing on the J516M uses it.
4. **Two tunable families never reach Linux**, because no node or alias
   receives them: `pcie_adapter_regs_tunables` (per ACIO) and
   `atc-apcie-{rc,fabric,debug}-tunables` plus `apcie-config-tunables` (per
   tunnel root port). m1n1 already copies both families. It needs only the
   aliases `usb4_N_pcie_adapter` and `usb4_N_pcie`.
5. Everything the Linux DT does describe matches the ADT, on all three ports:
   NHI, PDF, RC, DART, mailbox, IRQs, SIDs, power-domain registers and
   parents, LSTX pins and HPM SPMI addresses. The ADTs of J516C (T6031) and
   J516M (T6034) are identical for these nodes. They differ only in the router
   `vid-did`, Apple 0x200a against 0x200d.

## Port map

| Port | Socket (ADT `port-location`) | ADT nodes | Linux nodes |
|---|---|---|---|
| 0 | left-back (`hpm0`, `port-number` 1) | `acio0`, `dart-acio0`, `acio-cpu0`, `apciec0`, `dart-apciec0`, `apciec0-piodma`, `atc-phy0`, `atc0-dpin0/1` | `usb4_0_acio` (`t6031-dieX.dtsi:204`), `usb4_0_dart` (:227), `usb4_0_nhi` (:235), `usb4_0_mbox` (:190), `atcphy0` (:339) |
| 1 | left-front (`hpm1`, `port-number` 2) | `acio1`, …, `atc-phy1`, `atc1-dpin0/1` | `usb4_1_acio` (:380), `usb4_1_dart` (:403), `usb4_1_nhi` (:411), `usb4_1_mbox` (:366), `atcphy1` (:515) |
| 2 | right (`hpm2` on `nub-spmi-a1`, `port-number` 3) | `acio2`, …, `atc-phy2`, `atc2-dpin0/1` | `usb4_2_acio` (:556), `usb4_2_dart` (:579), `usb4_2_nhi` (:587), `usb4_2_mbox` (:542), `atcphy2` (:691) |
| (HDMI) | — | `atc-phy3` (`port-type` 6), `atc3-dpxbar`, `atc3-dpphy`; **no** `acio3`, `apciec3`, `usb-drd3`, `atc3-dpin*` | `atcphy3` (HDMI dtsi) |

ATC3 drives only the HDMI port. The J516M has exactly three USB4 ports, and
Linux is right to describe three ACIOs.

## Mismatches common to all three ports

Each item below holds on every port with the per-port values given in the
next section. N is the port (0, 1, 2). The address prefix P is 0x7, 0xb or
0xf, so port 0's 0xP01e44000 is 0x701e44000.

### M1: missing node: tunnel root port (`apciecN`)

ADT `/arm-io/apciecN`: `device_type = "pci-c"`, `compatible = "apciec,t8122"`.
Linux has no equivalent for the T6031/T6034. `t6031-dieX.dtsi` stops at ACIO,
DWC3, ATC PHY and crossbar, and `t6034-j516m.dts:12-16` includes no tunnel
dtsi. The J516S equivalent (port 0 only) is `usb4_0_pcie` at
`t6030-usb4.dtsi:68-127`.

The ADT reg order matches the J516S `reg-names` order, except that
`oe-fabric` is missing:

| ADT `apciecN` reg | J516S `reg-names` | Port 0 | Port 1 | Port 2 |
|---|---|---|---|---|
| [0] | `config` | 0x730000000 +0x10000000 | 0xb30000000 | 0xf30000000 |
| [1] | `rc` | 0x720000000 +0x4000 | 0xb20000000 | 0xf20000000 |
| [2] | `port0` | 0x721000000 +0x8000 | 0xb21000000 | 0xf21000000 |
| [3] | `fabric` | 0x720004000 +0x4000 | 0xb20004000 | 0xf20004000 |
| [4] | `debug` | 0x720200000 +0x4000 | 0xb20200000 | 0xf20200000 |
| [5] | `ltssm` | 0x721010000 +0x4000 | 0xb21010000 | 0xf21010000 |
| [6] | `intr2axi` | 0x72100c000 +0x4000 | 0xb2100c000 | 0xf2100c000 |
| `apciecN-piodma` reg[3] | `oe-fabric` | 0x720008000 +0x4000 | 0xb20008000 | 0xf20008000 |

Other `apciecN` properties the Linux tunnel node would need:

- `interrupts`: port 0 = 1347, 1350, 1351, 1352, 1353; port 1 = 1375,
  1378–1381; port 2 = 1403, 1406–1409. The J516S node uses only the first
  (`t6030-usb4.dtsi:82`). The other four are not consumed by any Linux
  binding.
- `ranges` (decoded):

  | | 64-bit prefetch (pci == cpu) | 32-bit MMIO (pci 0x00100000) | 32-bit prefetch (pci 0x40000000) |
  |---|---|---|---|
  | port 0 | 0x8_0000_0000 +0x2_0000_0000 | → 0xa_0010_0000 +0x3ff00000 | → 0xa_4000_0000 +0x40000000 |
  | port 1 | 0xc_0000_0000 +0x2_0000_0000 | → 0xe_0010_0000 | → 0xe_4000_0000 |
  | port 2 | 0x10_0000_0000 +0x2_0000_0000 | → 0x12_0010_0000 | → 0x12_4000_0000 |

  Port 0 is identical to the J516S `usb4_0_pcie` ranges
  (`t6030-usb4.dtsi:104-109`).
- **MSI**: every `apciecN` has `msi-vector-offset = 1854`,
  `#msi-vectors = 512`, `msi-address = 0xfffff000`. That pool is shared. The
  per-port slice is in the bridge child: `pcic0-bridge msi-vector-base = 32`,
  `pcic1-bridge = 64`, `pcic2-bridge = 96`, 32 vectors each. That gives AIC
  1886–1917, 1918–1949 and 1950–1981. The internal `apcie0` bridges take
  vectors 0–15, and Linux `pcie0` claims AIC 1854 ×32
  (`t6031-die0.dtsi:830`). Copying the J516S `msi-ranges` pattern (base equal
  to `pcie0`'s base, count 0x200: `t6030-usb4.dtsi:98` against
  `t6030.dtsi:1482`) would therefore overlap `pcie0` on the J516M. Use the
  per-bridge slices instead.
- `bus-range` cells (0, 0x80); `domain-id` = N+1.
- Power: `power-gates = <AUSBn-AONPCIE-V, ATCn_PCIE>` (ids 423/424/425,
  97/99/101); see M3.
- Child `pcicN-bridge`: `PCI-Thunderbolt`, `IOPCITunnelLinkChange`,
  `pci-ignore-linkstatus`, `msi-for-bridges`,
  `default-apcie-options = 0x80100001`, `vm-force = 0x100_0000_0000`. The
  first four are macOS hints with no Linux equivalent, except that the J516S
  port node marks `external-facing` (`t6030-usb4.dtsi:114`).

### M2: missing node: tunnel DART and PIO-DMA (`dart-apciecN`, `apciecN-piodma`)

| | Port 0 | Port 1 | Port 2 |
|---|---|---|---|
| `dart-apciecN` reg / IRQ | 0x721008000 +0x4000 / 1348 | 0xb21008000 / 1376 | 0xf21008000 / 1404 |
| `apciecN-piodma` reg / IRQ | 0x722000000, 0x722004000, 0x722008000 (+0x720008000) / 1349 | 0xb22000000… / 1377 | 0xf22000000… / 1405 |

DART properties, the same on all three ports: `compatible = "dart,t8110"`,
`sid-count = 64`, `vm-base = 0x100_8000_0000`, `vm-size = 0x7ff00000`,
`dead-mappings = [0, 0x4000]` (DVA page 0 is reserved),
`page-size = 0x4000`, `dart-options = 55`. The PIO-DMA engine uses SID 15
(`apciec-piodma-sid`). With the J516S `iommu-map` (RID 0–63 → SID 0–63,
`t6030-usb4.dtsi:99-100`), SID 15 is shared with whatever RID maps to 15.
The ADT DVA window starts at 1 TiB + 2 GiB and is less than 2 GiB long.
That matters to the eGPU tickets: PR #188's identity windows have to fit it
or override it.

Linux has neither node for the T6031/T6034. The J516S has only port 0's
DART (`t6030-usb4.dtsi:49-66`) and no PIO-DMA node.

### M3: power domain: `ATCn_PCIE` not attached

ADT `acioN` `power-gates = <ATCn_CIO, ATCn_CIO_PCIE, ATCn_CIO_USB>`
(port 0: 96, 123, 124). `ATCn_PCIE` (97/99/101) belongs to `apciecN`. Linux
ACIO `power-domains` has the three CIO domains only
(`t6031-dieX.dtsi:213-215`, `389-391`, `565-567`). `ps_atc0_pcie`,
`ps_atc1_pcie` and `ps_atc2_pcie` exist (`t6031-pmgr.dtsi:1771`, `1789`,
`1807`) at the ADT offsets 0x4b8/0x4c8/0x4d8 under `ATCn_COMMON`, but no
J516M node uses them. The J516S attaches `ps_atcN_pcie` to every ACIO
(`t6030-usb4.dtsi:10-13`, `22-25`, `34-37`). `AUSBn-AONPCIE-V` (423–425) and
`CIOn-RECONFIG-V` (419–421, ACIO and `acio-cpuN` clock-gate) are virtual
pmgr devices with no `ps-regs` slot. Linux needs no node for them.

### M4: address: ACIO `pcie-adapter` region

ADT `acioN` reg[5] = 0xP01e44000 +0x4000. Linux ACIO `reg` has only `rc`
and `sram` (`t6031-dieX.dtsi:206-208`, `382-384`, `558-560`). Without this
region the driver never maps the adapter or loads
`apple,tunable-pcie-adapter` (`drivers/thunderbolt/apple.c:3204-3226`), and
m1n1 has nowhere to put `pcie_adapter_regs_tunables` (see [Tunables Linux lacks entirely](#tunables-linux-lacks-entirely)). J516S:
`t6030-usb4.dtsi:7`, `19`, `31`.

### M5: address and firmware property: MxWrap `cpu` region and coprocessor type

ADT `acio-cpuN`: `compatible = "iop,mxwrap-acio"`, reg[0] = 0xP01108000
(mailbox), reg[1] = 0xP01100000 +0x4000 (wrapper CPU control). Every other ASC
in this ADT (`ans`, `sio`, `dcp`, `dcpext*`, `aop`) is `iop,ascwrap-v6`. The
`iop-acioN-nub` child carries `dont-power-on`, `no-firmware-service`,
`reconfig-firmware`, `user-power-managed = 1`, `watchdog-enable` and
`coredump-enable = 32`.

Linux describes only the mailbox (`t6031-dieX.dtsi:190-202`, `366-378`,
`542-554`). It has no `cpu` region on the ACIO. The J516S adds it as
`reg-names = "cpu"` (`t6030-usb4.dtsi:8`). The driver comment and match data
for T6031 say "no MxWrap region in its DT node" and set `.mxwrap = false`
(`drivers/thunderbolt/apple.c:154-160`). The ADT gives that region to the
T6034. The J516C (T6031) ADT has the same `iop,mxwrap-acio`. The DT omits the
region, but the hardware has it.

### M6: missing tunables

See [Tunables Linux lacks entirely](#tunables-linux-lacks-entirely). On
every port the destination node or the m1n1 alias is missing:
`t603x-j514-j516.dtsi:23-44` defines `usb4-N-acio`, `usb4-N-nhi`,
`usb4_N_rc` and `usb4_N_nhi`, but not `usb4_N_pcie_adapter` or
`usb4_N_pcie`. The J516S has these at
`t603x-j514s-j516s-usb4.dtsi:5-10`.

### M7: interrupts and regions the ADT has and Linux leaves out (low impact)

- **DP IN adapters**: ADT `atcN-dpin0/1` reg 0xP01e50000 / 0xP01e58000
  +0x4000, IRQs 1564/1565 (port 0), 1612/1613 (port 1), 1660/1661 (port 2).
  The driver reaches the registers as `rc` + 0x390000 + idx·0x8000
  (`drivers/thunderbolt/apple.c:359-361`, `660-665`), which matches the ADT.
  It enables the DP IN interrupts but has no handler, and the DT carries no
  IRQ for them. The J516S is the same.
- **NHI interrupt order**: the ADT lists the upper twelve first
  (port 0: 1552–1563, then 1540–1551). Linux names 1540–1551 `txring0-11` and
  1552–1563 `rxring0-11` (`t6031-dieX.dtsi:242-274`). The working J516S uses
  the same low = tx convention (`t6030.dtsi:1671`, NHI base 1099, DART 1126:
  the same layout), so this is treated as consistent. The ADT's
  `iommu-parent` order is tx-0…11 then rx-0…11 (SIDs 0–11 then 16–27). Check
  the IRQ assignment first if ring interrupts ever misfire.
- **HPM interrupts**: the ADT `hpmN` has three IRQs, of `interrupt-type` 0, 2
  and 3 (hpm0: 11, 17, 19; hpm1: 37, 43, 45; hpm2: 63, 69, 71; hpm5: 89, 95,
  97). Linux lists four, adding a `select` IRQ 13/39/65/91 that the ADT does
  not have (`t603x-j514-j516.dtsi:319-322`, `359-362`, `411-414`, `399-402`).
  The HPMs already bind, so this is not a blocker.

## Per-port lists

### Port 0: left-back (`acio0`, `atc-phy0`, `hpm0`)

| # | Kind | ADT | Linux |
|---|---|---|---|
| 0.1 | missing node | `/arm-io/apciec0`: regs in M1, IRQ 1347 (+1350–1353), MSI AIC 1886–1917, `domain-id 1` | none (`t6031-dieX.dtsi`, `t6034-j516m.dts:12-16`) |
| 0.2 | missing node | `/arm-io/dart-apciec0` 0x721008000, IRQ 1348 | none |
| 0.3 | missing node | `/arm-io/apciec0-piodma` 0x722000000/4000/8000 + 0x720008000, IRQ 1349 | none |
| 0.4 | power domain | `apciec0 power-gates = <423 AUSB0-AONPCIE-V, 97 ATC0_PCIE>` | `ps_atc0_pcie` defined (`t6031-pmgr.dtsi:1771`), not consumed; ACIO has 3 domains (`t6031-dieX.dtsi:213-215`) |
| 0.5 | address | `acio0` reg[5] 0x701e44000 +0x4000 | absent from `usb4_0_acio` `reg` (`t6031-dieX.dtsi:206-208`) |
| 0.6 | address / firmware | `acio-cpu0` `iop,mxwrap-acio`, reg[1] 0x701100000 +0x4000 | no `cpu` reg; mailbox only (`t6031-dieX.dtsi:190-202`) |
| 0.7 | tunable | `acio0 pcie_adapter_regs_tunables`; `apciec0 atc-apcie-{rc,fabric,debug}-tunables`, `apcie-config-tunables` | no `usb4_0_pcie_adapter` or `usb4_0_pcie` alias (`t603x-j514-j516.dtsi:23-44`) |
| 0.8 | interrupt (low) | `atc0-dpin0/1` IRQ 1564/1565 | not described |
| 0.9 | interrupt (low) | `hpm0` IRQs 11, 17, 19 | 11, 13, 17, 19 (`t603x-j514-j516.dtsi:319-322`) |

### Port 1: left-front (`acio1`, `atc-phy1`, `hpm1`)

| # | Kind | ADT | Linux |
|---|---|---|---|
| 1.1 | missing node | `/arm-io/apciec1`: 0xb30000000 config, 0xb20000000 rc, …; IRQ 1375 (+1378–1381), MSI AIC 1918–1949, `domain-id 2` | none. The J516S also has no port-1 tunnel. |
| 1.2 | missing node | `/arm-io/dart-apciec1` 0xb21008000, IRQ 1376 | none |
| 1.3 | missing node | `/arm-io/apciec1-piodma` 0xb22000000/4000/8000 + 0xb20008000, IRQ 1377 | none |
| 1.4 | power domain | `apciec1 power-gates = <424 AUSB1-AONPCIE-V, 99 ATC1_PCIE>` | `ps_atc1_pcie` (`t6031-pmgr.dtsi:1789`) unused; ACIO domains `t6031-dieX.dtsi:389-391` |
| 1.5 | address | `acio1` reg[5] 0xb01e44000 +0x4000 | absent (`t6031-dieX.dtsi:382-384`) |
| 1.6 | address / firmware | `acio-cpu1` `iop,mxwrap-acio`, reg[1] 0xb01100000 | mailbox only (`t6031-dieX.dtsi:366-378`) |
| 1.7 | tunable | as 0.7 for `acio1` / `apciec1` | no `usb4_1_pcie_adapter` or `usb4_1_pcie` alias |
| 1.8 | interrupt (low) | `atc1-dpin0/1` IRQ 1612/1613 | not described |
| 1.9 | interrupt (low) | `hpm1` IRQs 37, 43, 45 | 37, 39, 43, 45 (`t603x-j514-j516.dtsi:359-362`) |

### Port 2: right (`acio2`, `atc-phy2`, `hpm2` on `nub-spmi-a1`)

| # | Kind | ADT | Linux |
|---|---|---|---|
| 2.1 | missing node | `/arm-io/apciec2`: 0xf30000000 config, 0xf20000000 rc, …; IRQ 1403 (+1406–1409), MSI AIC 1950–1981, `domain-id 3` | none |
| 2.2 | missing node | `/arm-io/dart-apciec2` 0xf21008000, IRQ 1404 | none |
| 2.3 | missing node | `/arm-io/apciec2-piodma` 0xf22000000/4000/8000 + 0xf20008000, IRQ 1405 | none |
| 2.4 | power domain | `apciec2 power-gates = <425 AUSB2-AONPCIE-V, 101 ATC2_PCIE>` | `ps_atc2_pcie` (`t6031-pmgr.dtsi:1807`) unused; ACIO domains `t6031-dieX.dtsi:565-567` |
| 2.5 | address | `acio2` reg[5] 0xf01e44000 +0x4000 | absent (`t6031-dieX.dtsi:558-560`) |
| 2.6 | address / firmware | `acio-cpu2` `iop,mxwrap-acio`, reg[1] 0xf01100000 | mailbox only (`t6031-dieX.dtsi:542-554`) |
| 2.7 | tunable | as 0.7 for `acio2` / `apciec2` | no `usb4_2_pcie_adapter` or `usb4_2_pcie` alias |
| 2.8 | interrupt (low) | `atc2-dpin0/1` IRQ 1660/1661 | not described |
| 2.9 | interrupt (low) | `hpm2` IRQs 63, 69, 71 | 63, 65, 69, 71 (`t603x-j514-j516.dtsi:411-414`) |

### Not tied to one port

- **VDD_CIO rail**: ADT `/arm-io/pmgr` has `vdd-cio-rail-pg = 1` and
  `function-toggle_vdd_cio` pointing at `smc-pmu` with SMC key `pmVC`.
  `pmgr/soc-tuner` has `vdd-cio-pg = 0` and `cio-config = 1`. Linux, m1n1
  and the thunderbolt driver do not model this rail at all, on any board.
  The ACIOs and ATC PHYs already bind with the rail as iBoot left it, so it is
  probably on at boot. It becomes relevant if Linux ever powers ACIO down
  across s2idle.
- **Router device id**: ADT `acioN vid-did` = 0x200d05ac (J516M) against
  0x200a05ac (J516C). Linux has no DT property for it. The driver reads the
  id from the router's config space, and no quirk keys on 0x200a or 0x200d.

## Tunables Linux lacks entirely

The names come from m1n1's copy tables
(`m1n1-aurora/src/m1n1/src/kboot.c:1555-1584`, `1734-1772`, `1776-1843`).
m1n1 copies them for whichever `acioN`/`apciecN` exist, and only when the
Linux DT has the alias.

| ADT node | ADT property (iBoot-inserted) | Linux destination | On J516M today |
|---|---|---|---|
| `acioN` | `top_tunables`, `hbw_fabric_tunables`, `lbw_fabric_tunables` | `apple,tunable-rc` on ACIO | **present** (live DT, 360 B) |
| `acioN` | `hi_up_{tx_desc,tx_data,rx_desc,wr,merge}_fabric_tunables`, `hi_dn_merge_fabric_tunables`, `fw_int_ctl_management_tunables` | `apple,tunable-nhi` on NHI | **present** (live DT, 2712 B) |
| `acioN` | `thunderbolt-drom` | `apple,thunderbolt-drom` | **present** (76 B, the same length as the ADT) |
| `atc-phyN` | `tunable_ATC0AXI2AF`, `tunable_ATC_FABRIC`, `tunable_*PLL*`, `tunable_*AUSPMA*`, … | `apple,tunable-axi2af`, `-common-b`, `-lane{0,1}-{usb,cio}` | **present** |
| `acioN` | `pcie_adapter_regs_tunables` | `apple,tunable-pcie-adapter` on ACIO | **missing**: no `pcie-adapter` reg (M4), no `usb4_N_pcie_adapter` alias |
| `apciecN` | `atc-apcie-rc-tunables` | `apple,tunable-rc` on tunnel root port | **missing**: no node (M1) |
| `apciecN` | `atc-apcie-fabric-tunables` | `apple,tunable-fabric` | **missing** |
| `apciecN` | `atc-apcie-debug-tunables` | `apple,tunable-debug` | **missing** |
| `apciecN` | `apcie-config-tunables` | `apple,tunable` on the port child | **missing** |
| (none named) | oe-fabric block at 0xP20008000 | `apple,tunable-oe-fabric` | **missing**. The J516S hard-codes port 0's (`t6030-usb4.dtsi:89-95`) because m1n1 does not fill it. |
| (none named) | tunnel DART init | `apple,tunable` on the tunnel DART | **missing**. The J516S hard-codes it (`t6030-usb4.dtsi:56-65`), "No bootloader fills this one". |

The last two rows have no ADT property that m1n1 knows of. The J516S values
came from elsewhere, and whether they carry over to the T6034 is open (see
Gaps).

## What matches (checked, no action)

On every port:

- NHI 0xP01f00000 +0x100000.
- PDF 0xP01db0000 +0x30004.
- RC 0xP01ac0000 +0xc000 (ADT reg[2..4], three 0x4000 blocks matching
  m1n1's top/hbw/lbw offsets).
- `dart-acioN` 0xP01a80000 with IRQ 1567/1615/1663, SIDs 0–11 and 16–27, and
  `vm-base` 1 TiB (Linux iommus `0x100 0x0`).
- Mailbox at 0xP01108000 with IRQs 859–862, 867–870 and 875–878. The ADT lists
  them in its usual n+1, n, n+3, n+2 ASC order, the same as `dcp`/`ans`/`sio`.
- NHI IRQ blocks 1540–1563, 1588–1611 and 1636–1659.
- Power domains `ATCn_CIO` (0x4b0/0x4c0/0x4d0) → `ATCn_COMMON`, and
  `ATCn_CIO_PCIE` / `ATCn_CIO_USB` (0x598–0x5c0) → `ATCn_CIO`.
  `ATC0_COMMON` → `AFNC2_LW0`; `ATC1/2/3_COMMON` → `AFNC2_LW1`.
  `ATCn_USB` → `ATCn_USB_AON` + `ATCn_COMMON`. All of these offsets and
  parents equal `t6031-pmgr.dtsi`.
- ATC PHY clock-gates `ATCn_USB_AON` and `ATCn_COMMON`, covered by
  `ps_atcN_usb`.
- LSTX GPIO: ADT `gpio-lstx` gives AOP pins 55, 57 and 59, the same as
  `acioN_pins` (`t6031-dieX.dtsi:107-117`).
- HPM SPMI addresses 0xc, 0xa, 0x8 and 0x6, and the socket labels.
- ACIO `portmap`: adapters 1–2 lane, 3 PCIe, 4 USB3, 5–6 DP, matching the
  port comments at `t603x-j514-j516.dtsi:454-466`.

Linux uses two regions the ADT does not list on its own. The ACIO `sram`
region (0xP01080000 +0x20000) lies inside `atc-phyN` reg[29] (the 16 MiB
0xP00000000 window). The ATC PHY `lpdptx` (0xP03050000) appears in no
T6034 ADT reg. Neither is new and neither is USB4-specific; they are listed
only for completeness.

## T6031 against T6034

The `j516c` and `j516m` ADTs are identical for every node in
`acio*`, `dart-acio*`, `acio-cpu*`, `apciec*`, `dart-apciec*`, `atc-phy*`,
`atc*-dp*`, `usb-drd*` and `hpm*`: regs, IRQs, power-gates and properties.
The only differences are phandle values and `vid-did`. Every mismatch above
therefore applies to the J516C as well. None of them is caused by the T6034
reusing T6031 DT nodes.

## Gaps

- **No live ADT.** The tunable blocks in the "missing" rows of the tunables table and any DART tunables are
  iBoot-inserted. To confirm that `pcie_adapter_regs_tunables` and
  `atc-apcie-*-tunables` exist on the J516M, and to read the oe-fabric and
  tunnel DART values, the live ADT has to be dumped: m1n1 proxy, or a debug
  print in m1n1's `dt_copy_*`. Read-only work on the running Linux cannot see
  it; `/proc/device-tree` shows only what m1n1 copied.
- The meaning of the four extra `apciecN` IRQs (1350–1353 on port 0) and of
  the pmgr `vdd_cio` toggle is not established.
- The NHI tx/rx IRQ order is consistent with the J516S only by analogy. This
  note does not prove it from the ADT.
- The `cio_reset` bit layout (`t6031-dieX.dtsi`, `pmgr_cio` +0x2028) is
  not described in the ADT and was not checked.
