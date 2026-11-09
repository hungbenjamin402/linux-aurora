# Why no NHI binds on the J516M

Ticket: hungbenjamin402/linux-aurora#2 (map #1). Machine: J516M (T6034), kernel
7.2.11-15-1.900-ARCH built from branch `usb4-m3max` (7369b2d68bbd). Terms follow
`wayfinder/usb4-m3max/GLOSSARY.md`.

Each claim is marked **observed** (seen in source, the live device tree, sysfs,
the journal or the J516M ADT) or **inferred** (reasoned, not yet seen on hardware).

## Answer

Nothing is wrong with NHI matching. The NHI platform devices are never
created, because the driver creates them only while a port is in USB4 or
Thunderbolt mode. `thunderbolt-apple-acio` populates the ACIO's children
(the DART and the NHI) in `apple_cio_start()`. That function runs only when
the PD controller reports USB4/TBT mode entry through
`typec_thunderbolt_switch_set()`. No USB-C partner has been attached during
any retained boot, so no ACIO has started and there is no NHI device for
`thunderbolt-apple-nhi` to bind. The J516S works the same way: its NHIs
also bind only on connect.

The real bring-up gap is what happens when a dock is attached. The T6031
ACIO is driven with the M1 (t8103) start sequence. The J516M ADT shows its
ACIO co-processor is an MxWrap IOP at the same addresses as the T6030's.
The T6030 needs an explicit MxWrap RUN, LSTX control and a strict
firmware-ready check. Without them (**inferred**), `apple_cio_start()` will
fail at RTKit boot before it populates the NHI, even with a dock attached.

## Evidence: why there is no NHI device today

1. **The NHI is created on demand, not at boot** (observed, source).
   - `drivers/thunderbolt/apple.c:52-63`: the documented sequence is "configure
     PHY -> `typec_thunderbolt_switch_set()` -> power ACIO, boot RTKit, apply
     tunables -> **probe the DART and NHI children** -> register USB4 domain".
   - `apple.c:3118-3311` (`apple_cio_probe`) never calls `of_platform_populate`.
   - The only populate of the ACIO node is `apple.c:2696`
     (`of_platform_populate(acio->np, ...)`), inside `apple_cio_start()`
     (`apple.c:2554`), reached only from `apple_cio_tbt_switch_set()`
     (`apple.c:2896`, call at `apple.c:2986`) when `target_cable_info != 0`.
   - The caller is the PD controller driver: `drivers/usb/typec/tipd/core.c:684,
     711, 744`, on `TPS_DATA_STATUS_TBT_CONNECTION` /
     `CD321X_DATA_STATUS_USB4_CONNECTION`.

2. **No NHI platform device exists, but the match is fine** (observed, live).
   ```
   $ tr '\0' ' ' < /proc/device-tree/soc/cio@701ac0000/nhi@f00000/compatible
   apple,t6031-usb4-nhi apple,t8103-usb4-nhi        # matches apple_nhi_match (apple.c:2397-2405)
   $ ls /sys/bus/platform/devices/701ac0000.cio/
   consumer:typec:port1 driver ... typec_mux uevent  # no child devices
   $ ls /sys/bus/platform/devices | grep -E 'nhi|f00000'
   702f00000.iommu b02f00000.iommu f02f00000.iommu   # USB DARTs outside the ACIO, not NHIs
   $ sudo cat /sys/kernel/debug/devices_deferred      # empty
   ```
   `thunderbolt_apple`, `thunderbolt`, `typec`, `phy_apple_atc` and
   `tps6598x_core` are loaded. The PD controllers (`spmi 1-0c`, `1-0a`,
   `2-08`) are bound to `sn201202x` after a transient boot-time deferral
   (journal: `deferred probe pending`, later bound).

3. **No partner is on any USB-C port, and none appears in any retained boot**
   (observed).
   - `/sys/class/typec/port{1,2,3}` have no `-partner` entries. Only `port0`
     (`usb-pd@6`, the MagSafe controller, data role fixed `[device]`) has one.
   - Ports map as `usb-pd@c -> cio@701ac0000`, `usb-pd@a -> cio@b01ac0000` and
     `usb-pd@8 (spmi-2) -> cio@f01ac0000` (fw_devlink lines in `journalctl -b -k`).
   - `journalctl -k` over all 14 retained boots (Nov 8-9) has no `.cio`, RTKit-ACIO,
     `thunderbolt` or `usb N-M: new ... device` lines. Every failure path in
     `apple_cio_start()` logs with `dev_err` (for example "M3 RTKit failed to
     boot" or "Timed out waiting for the NHI"). Journald gets every level, so
     `loglevel=0` only quiets the console. So no start has ever been attempted
     under this kernel.

4. **Everything the NHI probe needs from the device tree is already there**
   (observed). m1n1 has filled these properties for all three ACIOs:
   - `apple,tunable-rc`: 360 B
   - `nhi@f00000/apple,tunable-nhi`: 2712 B
   - `apple,thunderbolt-drom`: 76 B
   - ATC PHY `apple,tunable-lane{0,1}-cio`: 588 B each

   The NHI node has 24 ring IRQs (12 tx, 12 rx, 4-cell specifiers) and 24
   `iommus` entries. The CIO reset (`apple,t6031-cio-reset`,
   `apple,t6000-cio-reset`) is bound to `apple-cio-reset`. ACIO power
   domains: the DT lists `ps_atcN_cio`, `ps_atcN_cio_pcie` and
   `ps_atcN_cio_usb`. These match the ADT `acio0` power-gates
   `[96 ATC0_CIO, 123 ATC0_CIO_PCIE, 124 ATC0_CIO_USB]`.

## Evidence: what will fail when a dock is attached

5. **The T6031 ACIO is given the t8103 start sequence** (observed, source).
   - `apple.c:154-160`:
     ```c
     /* The T6031 (M3 Max) ACIO boots like t8103 (no MxWrap region in its DT
      * node) ... */
     static const struct apple_cio_hw apple_cio_t6031_hw = { .dp = &apple_dpin_m3_max, };
     ```
   - T6030 has `.mxwrap = true, .lstx_explicit = true, .strict_fw_ready = true`
     (`apple.c:147-152`).
   - The flags select these paths in `apple_cio_start()`:
     - `lstx_explicit` writes `LSTX_CTRL_ENABLE|LEVEL` to `rc+0x0c` instead of
       OR-ing `M3_CTRL_START` (`apple.c:2631-2637`).
     - `mxwrap` sets `RUN` (bit 4) in MxWrap `cpu+0x28` (`apple.c:2639-2644`).
     - `strict_fw_ready` waits for STATE==READY and decodes firmware asserts
       (`apple.c:2660-2675`).
   - Commit abbc8264bc0b ("apple: run Thunderbolt DP tunnels on T6031")
     justified the t8103 choice by the missing `cpu` region in the DT node. The
     T6030 base node has no `cpu` region either (`t6030.dtsi:1633-1640`,
     `reg-names = "rc", "sram"`). The T6030 gets it only from the overlay
     `t6030-usb4.dtsi:4-14` (`reg-names = "rc", "sram", "pcie-adapter", "cpu"`).
     The reasoning is circular: no T6031 counterpart of `t6030-usb4.dtsi` exists.

6. **The J516M ADT says the ACIO co-processor is MxWrap, at the T6030 addresses**
   (observed, `~/aurora-test/ipsw/dt/j516m.json`, macOS 26B123; arm-io ranges
   are identity for 0x7_0000_0000+):

   | ADT node | compatible | reg | T6030 DT equivalent |
   |---|---|---|---|
   | `acio-cpu0` | `iop,mxwrap-acio` | `0x701108000` (mailbox), **`0x701100000`** | `"cpu"` = `0x7_01100000` |
   | `acio0` | `acio` | ..., `0x701ac0000`, ..., **`0x701e44000`** | `"rc"`, `"pcie-adapter"` = `0x7_01e44000` |
   | `acio-cpu1` / `acio1` | same | `0xb01100000`, `0xb01e44000` | `0xb_01100000`, `0xb_01e44000` |
   | `acio-cpu2` / `acio2` | same | `0xf01100000`, `0xf01e44000` | `0xf_01100000`, `0xf_01e44000` |

   `acio0` also carries `gpio-lstx`, and the child `iop-acio0-nub` is
   `iop-nub,rtbuddy-v2` with `dont-power-on`. Its clock gate 419 is
   `CIO0-RECONFIG-V`; the T6030 DT does not model it either, and T6030 works.

7. **Expected failure when a dock enters USB4 today** (inferred). PD reports
   USB4, the PHY switches, and `apple_cio_start()` powers the domains and
   deasserts the reset. It then sets `M3_CTRL_START` but never sets MxWrap
   RUN, so the IOP does not run. `apple_rtkit_boot()` fails ("M3 RTKit failed
   to boot"), or the ready poll times out ("M3 firmware failed to get
   ready"). The function unwinds before `of_platform_populate` at
   `apple.c:2696`. The NHI still never appears.

   The driver cannot simply be switched to `mxwrap = true`. `apple_cio_probe()`
   then demands a `cpu` reg (`apple.c:3151-3157`, "Missing MxWrap cpu region").
   Without the DT change, the ACIO itself stops binding.

## What the T6030 (J516S) path does differently

| Item | T6030 / J516S | T6031 / J516M today |
|---|---|---|
| ACIO compatible / hw | `apple,t6030-usb4-acio` -> `mxwrap`, `lstx_explicit`, `strict_fw_ready` | `apple,t6031-usb4-acio` -> t8103 sequence (`apple.c:158`) |
| ACIO `reg-names` | `rc sram pcie-adapter cpu` (`t6030-usb4.dtsi`) | `rc sram` (`t6031-dieX.dtsi:204-216`) |
| ACIO power domains | `cio`, `cio_pcie`, `cio_usb`, **`atcN_pcie`** | `cio`, `cio_pcie`, `cio_usb` |
| `usb4_N_pcie_adapter` aliases (m1n1 fills `apple,tunable-pcie-adapter`, `kboot.c:1759-1764`) | yes (`t603x-j514s-j516s-usb4.dtsi`) | no (not in `/proc/device-tree/aliases`) |
| Tunnel root port (`apple,pcie-tunnel`, `usb4_0_pcie` alias for m1n1 PCIe-C tunables, `kboot.c:1829-1843`) | port 0 only (`t6030-usb4.dtsi` `usb4-pcie-tunnel-0`) | none (ADT has `apciec0/1/2` at `0x730000000`/`0xb30000000`/`0xf30000000`, same layout as T6030) |
| Machine compatible used by SoC gates | `apple,t6030` | `apple,j516m`, `apple,t6034`, **no `apple,t6031`** |
| PD controller, ATC PHY, CIO reset, NHI node | shared code: sn201202x/tipd, `t8122-atcphy`, `t6000-cio-reset`, `t8103-usb4-nhi` | same |

Gates keyed on `apple,t6031`/`apple,t6030` that the J516M root does not match
(observed). These do not block bring-up, but they matter for later tickets:
- `apple.c:386-387`: `apple_dpin_qualified_soc` lists `apple,t6031`, but the
  J516M root is `apple,t6034`, so DP IN tunnels stay disabled.
- `drivers/pci/controller/pcie-apple.c:1879` and `:3251`: T6030-only ECAM slice
  and `t8122_pciec_hw` selection. These matter for the tunnel root port.
- `drivers/phy/apple/atc.c:3228-3230` already lists `apple,j516m` explicitly.

## Change list

For **bring-up** (NHI binds, USB4 domain and host router appear on a dock attach):

1. **kernel (DT)**: add a T6031 USB4 overlay, modelled on `t6030-usb4.dtsi`.
   - For each `usb4_N_acio` (N=0,1,2 at 0x7/0xb/0xf), extend `reg` with
     `pcie-adapter` = `<0xN 0x01e44000 0 0x4000>` and `cpu` =
     `<0xN 0x01100000 0 0x4000>`, with `reg-names = "rc", "sram",
     "pcie-adapter", "cpu"`.
   - Include it from `t6034-j516m.dts`, or from the T6031/T6034 SoC dtsi if
     J514M/J514C/J516C share the ADT layout. Their ADTs have not been checked.
2. **kernel (driver)**: give `apple_cio_t6031_hw` `.mxwrap = true,
   .lstx_explicit = true, .strict_fw_ready = true`, and fix the comment at
   `apple.c:154-157`.
   - Must land together with item 1 (see point 7).
   - Only `mxwrap` is ADT-backed. `lstx_explicit` and `strict_fw_ready` are
     **inferred** from the shared M3-generation IOP; `gpio-lstx` is present.
3. **kernel (DT, optional for bring-up)**: add `usb4_N_pcie_adapter` aliases,
   as in `t603x-j514s-j516s-usb4.dtsi`, so that m1n1 fills
   `apple,tunable-pcie-adapter`. The driver treats a missing tunable as
   optional (`apple.c:3218-3224`).
4. **m1n1: none needed for bring-up** (observed). The current m1n1 (`b05e6acd`)
   already fills `apple,tunable-rc`, `apple,tunable-nhi`,
   `apple,thunderbolt-drom` and the ATC PHY CIO lane tunables on the J516M.
   It also fills the pcie-adapter and PCIe-C tunables once the kernel DT
   provides the aliases.
5. **Hardware test** (not a code change): attach the USB4 dock to one port
   with `dyndbg` on `drivers/thunderbolt/apple.c` and
   `drivers/usb/typec/tipd/core.c`. Confirm the order: "set cable state", M3
   ready, NHI probe, `/sys/bus/thunderbolt/devices/domainN`. A failure at
   "M3 RTKit failed to boot" on the unpatched kernel would confirm point 7.

Needed after bring-up, for tunnels (listed here because they fall out of the
same comparison):

6. **kernel (DT)**: a 4th ACIO power domain `ps_atcN_pcie` (ADT `ATC0_PCIE`
   id 97 belongs to `apciec0`). Also tunnel root port nodes
   `usb4-pcie-tunnel-N`, `apple,pcie-tunnel` and `usb4_N_pcie` aliases for
   apciec0..2, copied from `t6030-usb4.dtsi` with T6031 IRQ numbers.
7. **kernel (driver)**:
   - Make `pcie-apple.c:1879/3251` accept the J516M (`apple,t6034` or
     `apple,j516m`).
   - Make `apple_dpin_qualified_soc` match the J516M root. It lists
     `apple,t6031`, but the root is `apple,t6034`.

## Not determined

- Whether the NHI binds once items 1 and 2 land. This needs a dock attach on
  hardware. No USB4/TBT partner was attached in any retained boot, so I could
  not watch the current start path fail. Point 7 is inference.
- Whether T6031 needs `lstx_explicit` and `strict_fw_ready`, or only `mxwrap`.
  No T6030 ADT was available locally to compare `acio-cpu` and `gpio-lstx`
  against.
- NHI ring IRQ order. The T6031 DT assigns txring0..11 = 1540-1551 and
  rxring0..11 = 1552-1563, the same "lower block = tx" convention as T6030
  (1099/1111). The ADT `acio0.interrupts` lists 1552-1563 first and then
  1540-1551. Without a T6030 ADT I cannot tell whether the ADT order is
  tx-first. A swap would not stop the NHI driver from binding, but it would
  break ring interrupts. Check it on the first attach.
- Whether the SN201202x firmware on the J516M enters USB4/TBT mode without
  host help, as on the J516S. The PD path is shared code. Assumed yes, not
  observed.
