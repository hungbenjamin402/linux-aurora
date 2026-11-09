# What macOS does to bring up USB4 on the T6034

Ticket: hungbenjamin402/linux-aurora#5 (map #1). Machine: J516M (T6034).
Terms follow `wayfinder/usb4-m3max/GLOSSARY.md`.

Every claim has a tag:

- **[observed]**: seen in the kernelcache disassembly, its symbols and log
  strings, in the J516M ADT dump, or in Linux or m1n1 source. Addresses are
  kernel virtual addresses in the kernelcache named below.
- **[inferred]**: reasoned from observed facts, not seen directly.

Nothing here has been tested on hardware.

## Answer

macOS runs the same kexts on the T6030 (M3 Pro) and the T6031/T6034
(M3 Max). The NHI kext is the same build on both. Bring-up is driven by
the ADT, not by chip-specific code. So the T6034 needs what the T6030
already gets in Linux, plus a few things neither of them gets.

For one port, macOS brings up USB4 in this order:

1. Put the ATC PHY in CIO mode.
2. Turn on the ACIO's clock and power gates.
3. Power the ACIO's MxWrap coprocessor and set it running.
4. Drive LSTX through the ACIO `rc` register.
5. Poll the firmware state register until it reads exactly READY.
6. Apply ten ADT tunable tables.
7. Turn on the tunnel power domains.
8. Start the NHI.

The PCIe tunnel root port starts later. It is switched on through a
platform function, `PrtC`, only after the host router's PCIe down adapter
is enabled.

What Linux is missing for the T6034, with where each fix goes:

1. **MxWrap RUN, LSTX level and strict firmware-ready check on T6031.**
   Linux drives the T6031/T6034 ACIO with the M1 start sequence
   (`drivers/thunderbolt/apple.c:154-160`). macOS starts it as an MxWrap
   IOP: it writes CPU_CTRL RUN, writes LSTX = 3 or 2 to `rc`+0x0c, and
   waits for STATE == 1 at `rc`+0xa8. The fix is `apple_cio_t6031_hw`,
   plus a `cpu` reg on the T6031 ACIO nodes (`t6031-dieX.dtsi`).
   [observed in macOS code]
2. **ACIO PCIe-adapter region, its tunable, and the PCIe tunnel root port
   DT for the T6031.** Only the T6030 has them, in `t6030-usb4.dtsi`.
   See "PCIe tunnel root port" below.
3. **NHI fabric tunables are written to swapped blocks.** For every chip
   except T8142, m1n1's `usb4_nhi_tunables` swaps the `hi_up_tx_desc` and
   `hi_up_rx_desc` targets: it uses 0xf0000 and 0xe8000, where macOS uses
   0xe8000 and 0xf0000. This is in m1n1 `src/kboot.c:1556-1558`. The
   Linux NHI driver applies whatever m1n1 hands it. [observed in both
   sources; the effect is unknown]
4. **ATC PHY CIO mode details.**
   - The EQ_CDRLOCK_ON_START_EN clear is missing.
   - The reset delays and the tunable order differ.
   - The lane tunables follow plug orientation, which macOS does not do.

   All of these are in `drivers/phy/apple/atc.c`. See "ATC PHY".
5. **CIO reconfigure timeout.** macOS waits up to 10 s for the reconfigure
   to complete, sleeping 20 ms between polls. Linux gives up after 100 ms
   (`drivers/reset/reset-apple-cio.c:58`). Then `apple_cio_start()`
   rewrites the request up to 5 times. [observed]

The full list, with confidence for each item, is under "Steps Linux lacks".

## Source and method

- **Kernelcache:** `kernelcache.release.Mac15,8_9_10_11_14` from macOS
  27.2 (26B123), `xnu-13432.41.4`, `RELEASE_ARM64_T6031`. It is the
  decompressed form of the extracted `kernelcache.release.mac15j` for
  Mac15,11.
- **Other kernelcaches:** the T6030 (`Mac15,6_7`) and T6020/T6021
  (`Mac14,5_…`) kernelcaches from the same IPSW, used for the generation
  comparison.
- **Tools:** `ipsw` 3.1.743 was used for:
  - `kernel kexts --json` to read IOKit personalities;
  - `kernel extract` to pull out each kext. The extracted kexts keep their
    local C++ symbols, so function names are real;
  - `kernel cpp --methods` to read vtables, which name the virtual calls;
  - `macho disass` to disassemble. Stub targets were resolved against the
    symbol tables of the kernel and the kexts.
- **ADT:** the J516M and J516C ADT JSON dumps already in the session
  scratchpad. In those dumps the ACIO and PHY tunables are filled in by
  iBoot at boot and are absent. The live values come through m1n1.
- **Not published:** no Apple binary and no disassembly beyond single
  register offsets and constants.

## Kexts and what they bind to on the J516M

| ADT node (J516M) | compatible | kext | IOKit class |
|---|---|---|---|
| `acio0..2` | `acio` | `com.apple.driver.AppleThunderboltNHI` 7.2.81 | `AppleThunderboltHALType5` (HAL), which creates `AppleThunderboltNHIType5` (NHI, a subclass of `AppleThunderboltNHIGenericACIO`) |
| `acio-cpu0..2` | `iop,mxwrap-acio` | `com.apple.driver.AppleA7IOP-MXWrap-v1` | `AppleMxWrapACIO` |
| `acio-cpuN/iop-acioN-nub` | `iop-nub,rtbuddy-v2` | `com.apple.driver.RTBuddy` | `RTBuddy` |
| `atc-phy0..3` | `atc-phy,t8122` | `com.apple.driver.AppleT8122TypeCPhy` (+ `AppleTypeCPhy`) | `AppleT8122TypeCPhy` |
| `apciec0..2` | `apciec,t8122` | `com.apple.driver.AppleT8122PCIeC` | `AppleT8122PCIeC` |
| `apciecN/pcicN-bridge` | `pciec-bridge` | `com.apple.driver.AppleT8122PCIeC` | `ApplePCIECHostBridge` |
| `apciecN-piodma` | `pciec-apiodma,t6020` | `com.apple.driver.AppleT6020PCIeCPIODMA` | `ApplePCIeCPIODMA` |
| `dart-acioN`, `dart-apciecN` | `dart,t8110` | `com.apple.driver.AppleT8110DART` | `AppleT8110DART` |
| `nub-spmi-a0/hpm0…` | `usbc,sn201202x,spmi` | `com.apple.driver.AppleHPM` | `AppleHPMARMSPMI` |
| `i2c6/atcrt0..2` | `atcrt` | `com.apple.driver.AppleTypeCRetimer` | `AppleTypeCRetimer` |
| tunnel adapters | (IOThunderboltPort) | `AppleThunderboltPCIDownAdapter` etc. | `AppleThunderboltPCIDownAdapterType5` |

[observed: `kernel kexts --json` personalities, matched against the ADT
`compatible` values]

Notes:

- `AppleT6032TypeCPhy` and `AppleT6032PCIeC` match only `atc-phy,t6032`
  and `apciec,t6032` (M3 Ultra). The J516M does not use them. [observed]
- The ACIO M3 firmware images (`t8103_acio_text/data`, `tmu_text/data`)
  are built into the NHI kext. They are loaded only when `acio` boot-arg
  bit 15 is set (`loadFirmware`, gated in `enableEmbeddedCPU`). In normal
  boots the firmware comes from iBoot. [observed]
- The tunable tables built into the kext (`acio_*_tunables_block`) are
  published only when `acio` boot-arg bit 24 is set (`publishTunables`).
  In normal boots the tables come from the ADT, which iBoot fills in.
  [observed]
- The `acio` boot-arg is parsed into `this+0x118` and defaults to 0. Every
  quirk path gated on it is off in production. That includes the
  hard-coded physical writes in `enableEmbeddedCPU` (to `0x2922dc21c`,
  `0x28e099068` and `0x28e09a034`, `0x23b788000`). [observed]

## Generations: T6030 vs T6031/T6034 vs T6020/T6021

[observed from the kext lists of the three kernelcaches]

| | T6020/T6021 (M2 Pro/Max) | T6030 (M3 Pro) | T6031/T6034 (M3 Max) |
|---|---|---|---|
| NHI kext | AppleThunderboltNHI 7.2.81 | same | same |
| ACIO coprocessor wrapper | ASCWrap-v4 | MXWrap-v1 (`iop,mxwrap-acio`) | MXWrap-v1 (`iop,mxwrap-acio`, J516M and J516C ADT) |
| ATC PHY kext | AppleT8112TypeCPhy | AppleT8122TypeCPhy | AppleT8122TypeCPhy |
| PCIe-C kext | AppleT6000PCIeC | AppleT8122PCIeC | AppleT8122PCIeC |
| PMGR CIO reconfigure / VDD_CIO | AppleT6020PMGR has them | AppleT6030PMGR has them | AppleT6031PMGR has them (`pmgr_cio`+0x2028) |

What is specific to the T603x generation, compared with the T6020/T6021,
is the MxWrap coprocessor and the T8122-class PHY and PCIe-C. That
includes the PHY's CIO tunable set and the `oe-fabric`/`intr2axi`
PCIe-C blocks. Between the T6030 and the T6031/T6034, macOS has no code
difference in these drivers. Every T6030/T6031 difference Linux has is a
choice made in Linux: the hw flags in `apple.c` and the DT nodes.
[inferred from the identical kexts and ADT compatibles]

## The macOS bring-up sequence for one port

### A. Probe, with no cable

`AppleThunderboltNHIGenericACIO::unpoweredStart` @0xfffffe000a13af6c:

1. Reads `enabled-ring-mask` and the boot-args `tb_hi_ring_mask` and
   `tb_phy_wait_ms`. [observed]
2. `setupPHY`: finds the PHY service. It derives `fChipType` from the PHY
   class: 2 if the PHY is `AppleT6000TypeCPhy`, else 1. The ACIO node has
   no `chip-type`. So on the T6034, `fChipType` = 1. [observed @a13b2ec-a13b348]
3. Looks up `gpio-lstx` through `AppleGPIOICController`. On the J516M,
   `gpio-lstx` is AOP pin 55/57/59, the same pins as Linux's
   `acioN_pins`. [observed]
4. `setupEmbeddedCPU`: resolves the `acio-cpu` phandle to the MxWrap IOP
   and its RTBuddy nub. The nub has `dont-power-on`,
   `user-power-managed = 1` and `reconfig-firmware`, so the NHI driver
   owns the IOP's power. With `reconfig-firmware`, RTBuddy skips its own
   power-on after a firmware load (`RTBuddy::loadFirmware` @0xfffffe000b78a068).
   [observed]
5. `createPowerDomainClientArray`: reads the ACIO `clock-gates`
   [96, 123, 124, 419] and `power-gates` [96, 123, 124]. In the pmgr
   `devices` table these are:
   - 96 = ATC0_CIO
   - 123 = ATC0_CIO_PCIE
   - 124 = ATC0_CIO_USB
   - 419 = CIO0-RECONFIG-V, a virtual device

   [observed in the ADT and in the code]
6. `setupCableStateTracking`. The HAL's `unpoweredStart` also resolves
   `function-dart_force_active` (`Fact` on `dart-acio0`),
   `function-exit_mode` and `function-dock_parent`. [observed]

### B. Cable attach: `setHWState(on)` @0xfffffe000a14189c

Every step below is [observed]. The ordered calls are:

1. **`setPhyState(2)`** puts the ATC PHY into CIO mode before the ACIO CPU
   starts. The PHY steps are in "ATC PHY" below.
2. **`enableEmbeddedCPU(true)`** @0xfffffe000a13edc8. This is the core of
   bring-up. With the `acio` boot-arg at 0, it does the following, in
   order:
   1. `setARMIODevicePowerState(7 /* on */, index)` for gate indices 0, 1,
      2 and then 4, each through `AppleARMIODevice` (@a13f02c-a13f0fc).
      Indices 0-2 are ATC0_CIO, ATC0_CIO_PCIE and ATC0_CIO_USB. Index 4 is
      not resolved; see the open questions.
   2. `fEmbeddedCPU->setPowerState(on)` (@a13f32c) powers the MxWrap IOP.
      The IOP has `clock-gates` [419] (CIO0-RECONFIG-V), and RTBuddy runs
      the firmware handshake on it.
      - The CPU is started by `AppleMxWrapACIO::_runCPU(true)`
        (@0xfffffe0008c1051c). If the IOP node has
        `function-reconfig_req_interrupt`, that PMGR trigger starts the
        CPU and runs the CIO reconfigure. The J516M ADT has no such
        property, so `_runCPU` falls through to `AppleMxWrap::_runCPU`,
        which writes **0x10 to wrapper +0x28** (CPU_CTRL.RUN). To stop the
        CPU it writes 0xffffffef.
      - The wrapper base is `acio-cpu0` reg[1] = **0x701100000**. reg[0],
        at 0x701108000, is the mailbox.
      - `_isIdle` reads wrapper +0x44 bit 1. `enablePower()` and
        `_apInitializesMailboxes()` both return 0.
   3. **LSTX:** it writes `rc`+0x0c = **3** if a cable is connected and
      **2** if not, through `registerWrite32ForRange(2, 0xc, v)`
      (@a13f64c → a13f9d8). Range 2 is ACIO reg[2], `0x701ac0000`, which is
      Linux's `rc`.
   4. It polls the firmware state through `getFirmwareState`, which is
      `registerRead32ForRange(2, 0xa8)` = `rc`+0xa8. Ready means
      **`(v & 0x7f000000) == 0x01000000`**. It polls every 5 ms
      (`IOSleep(5)`), with a deadline of N × 500 ms (@a13fae0-a13fb98).
      For USB4+ links it logs "skipping FW Ready delay".
   5. **Tunables:** it calls `applyTunables(fTunableReferences, 10)`
      (@a13fd78) only after the firmware reports ready. Each table is
      named, and the name is looked up as an ADT property:

      | ADT property | ACIO reg index | offset |
      |---|---|---|
      | `top_tunables` | 2 (`rc`, 0x701ac0000) | 0 |
      | `hbw_fabric_tunables` | 3 (0x701ac4000) | 0 |
      | `lbw_fabric_tunables` | 4 (0x701ac8000) | 0 |
      | `hi_up_tx_desc_fabric_tunables` | 0 (NHI, 0x701f00000) | **0xe8000** |
      | `hi_up_tx_data_fabric_tunables` | 0 | 0xec000 |
      | `hi_up_rx_desc_fabric_tunables` | 0 | **0xf0000** |
      | `hi_up_wr_fabric_tunables` | 0 | 0xf4000 |
      | `hi_up_merge_fabric_tunables` | 0 | 0xf8000 |
      | `hi_dn_merge_fabric_tunables` | 0 | 0xfc000 |
      | `fw_int_ctl_management_tunables` | 0 | 0x4000 |

      The PCIe adapter table is separate (`fPCIEAdapterTunableReferences`):
      `pcie_adapter_regs_tunables` goes to ACIO reg[5] (0x701e44000), and
      `pcie_router_ap_fw` to reg[6]. The J516M ADT has no reg[6].
      Each tunable entry is (offset, size, mask, value). Entries whose size
      is not 4 are skipped.
3. **`disableAllPowerDomains(false)`** turns on the tunnel client domains:
   the PCIe and USB clients added with `addPowerDomainClient`.
4. **`configureHardware(true)`** on the NHI starts the rings and the
   router.

`setHWState(off)` undoes this in reverse:

1. `configureHardware(false)`.
2. `disableAllPowerDomains(true)`.
3. `enableEmbeddedCPU(false)`. The LSTX level is saved first by reading
   `rc`+0x0c.
4. `setPhyState(0)`.
5. `IOSleep(50)`.

### C. CIO reconfigure and VDD_CIO in the PMGR

- **CIO reconfigure.** `AppleT6031PMGR::enableCioReconfig(cluster, on)`
  @0xfffffe0009f8be54 does three things:
  1. Waits for bit (16+n) of the PMGR CIO register at **+0x2028** to
     clear. The timeout argument is 0x2ee00.
  2. Writes bit n.
  3. Calls `ApplePMGR::waitForCioClusterComplete`, which polls until bit
     (16+n) clears. It sleeps 20 ms between reads, with a **10 s
     deadline**, after which it panics with "Cio cluster Failed to Come
     Online within 10 seconds".

  This is the register Linux drives as `cio_reset` (`pmgr_cio`+0x2028,
  `t6031-dieX.dtsi:51-55`). Linux's sequence matches, but Linux gives up
  after 100 ms. [observed]
- **What triggers it.** In this kernelcache, `enableCioReconfig` is reached
  only through `ApplePMGRFunctionReconfigTrigger` (the
  `function-reconfig_req_interrupt` platform function) and through the
  debug knobs in `AppleT6031SOCTuner`. The J516M ADT defines no
  `function-reconfig_req_interrupt`. So on the J516M, macOS may never ask
  for a CIO reconfigure at runtime, and iBoot's reconfigure at boot may be
  the only one. [observed that the property is absent; inferred meaning]
- **VDD_CIO.** The pmgr node has `vdd-cio-rail-pg = 1` and
  `function-toggle_vdd_cio`, which calls `pKW4` on `smc-pmu` with SMC key
  `pmVC`.
  - `AppleT6031PMGR::syncVddCioState` @0xfffffe0009f8c904 reads 8
    power-state registers (regmap 1, offsets 0xd0-0xe8). It keeps the rail
    on if any of them reads 0xf (on), and turns it off otherwise. It runs
    from `_triggerPostPowerOffActions` and from system sleep and wake.
  - So macOS gates the VDD_CIO rail off when every CIO power state is off.
  - Linux never touches `pmVC`. The rail stays as iBoot left it. That is
    harmless unless something else turns it off, for example the SMC
    across s2idle. [observed in code; inferred effect]
- The same three methods exist in AppleT6020PMGR and AppleT6030PMGR, so
  none of this is new in the T603x generation. [observed]

### D. ATC PHY: `AppleT8122TypeCPhy` in CIO mode

Working notes:
`/tmp/claude-1000/-home-ben/87888966-aece-447f-b603-cbd4008e2e02/scratchpad/kc-usb4/notes-phy.md`.

The T8122 PHY has no firmware and no mailbox (`supportACIO80Phy()` returns
0). The ACIO80 PHY firmware path exists only for the T6032. The code does
not depend on chip type, so the T6030 and T6031/T6034 run the same
sequence. [observed]

The call chain is `setPhyState(2)` → `AppleTypeCPhy::configureLanes` →
`initACIO` @0xfffffe000a27daa0 → `aciophy_phy_init` @0xfffffe000a2612f4:

1. **Power.** Turn on the PHY clock-gates, ATC0_USB_AON and ATC0_COMMON,
   with `setDevicePowerState(7, 0/1)`. [observed]
2. **Power-up and reset** (`aciophy_phy_powerup_rst` @0xfffffe000a25ff18).
   All registers are in ATCPHY_CFG (reg[28], 0x703020000):
   1. Set bit 0 at +8 (S2R_AON_SYNC_RST_N) and wait 1 µs.
   2. Set bit 0 at +0 (SLEEP_B_SML_IN) and poll +4 bit 0.
   3. Set bit 1 at +0 (SLEEP_B_BIG_IN) and poll +4 bit 1.
   4. Clear bit 2 (CLAMP_EN) and wait 1 µs.
   5. Set bit 3 (APB_RESET_N).

   [observed]
3. **CIO tunables** (`aciophy_apply_cio_tunables` @0xfffffe000a267024).
   Common tables first:
   - `tunable_ATC0AXI2AF`
   - `ATC_FABRIC`
   - `AUSCMN_DIG`
   - `AUSPLL_CORE`
   - `CIO3PLL_CORE`
   - `CIO3PLL_TOP`
   - `ACIOPHY_PLL_TOP`
   - `CIO_SHIM`
   - `ACIOPHY_TOP`

   Then, for each lane in the lane mask, in this order:
   1. `LNx_TX_SHM`, `RX_TOP`, `RX_SHM`, `TX_TOP` (`_CIO_DFLT`).
   2. A hard-coded clear of bit 1 at LNx RX_TOP+0x1e0
      (PMAFSM_RX_CTRL.EQ_CDRLOCK_ON_START_EN; @a26873c and @a2691a0).
   3. `LNx_RX_EQ_CIO_EQA`.

   [observed]
4. **Crossbar** (`aciophy_xbar_config(2)`). Clear the 12 lane-mode bits at
   ACIOPHY_TOP+0x60 (0 means CIO). Set ACIOPHY_TOP+0x64 bits [4:0] to 1 if
   the plug is flipped, else to 0. [observed]
5. **Efuse load.** Apply `tunable_AUSCMN_SHM`, then `tunable_CLKMON_CFG`.
   [observed]
6. **Reset release.** Wait 10 µs, set ATCPHY_CFG+0 bit 4 (ACIOPHY_RESET_N),
   then wait 100 µs. The common bias/RCAL init runs only in DP modes.
   [observed]

### E. PCIe tunnel root port

Working notes, with register tables:
`/tmp/claude-1000/-home-ben/87888966-aece-447f-b603-cbd4008e2e02/scratchpad/kc-usb4/notes-pciec.md`.

**Register blocks.** `AppleT8122PCIeC` (class `AppleTunneledPCIE`, port
`AppleT8122PCIeCPort` → `AppleT8103PCIeCPort` → `APCIECPort`) maps the
`apciec0` regs as follows:

| reg | address | block | Linux name |
|---|---|---|---|
| 0 | 0x730000000 | ECAM | `config` |
| 1 | 0x720000000 | common | `rc` |
| 2 | 0x721000000 | port | |
| 3 | | fabric | |
| 4 | | debug | |
| 5 | | LTSSM debug | |
| 6 | 0x72100c000 | Intr2AXI | |

The 0x720008000 block that Linux calls `oe-fabric` belongs to
`apciec0-piodma`. The port's power comes from `clock-gates`:

- 423 = AUSB0-AONPCIE-V, a virtual device aliased to ATC0_USB_AON;
- 97 = ATC0_PCIE.

[observed]

**Bring-up order:**

1. **Start.** `AppleTunneledPCIE::start` @0xfffffe000a00fc78:
   - Reads `msi-*`, `ltssm-timeout` and `link-state-power`.
   - Builds a 512-vector MSI controller at AIC 1854, plus 4 INTx lines.
   - Caches the `apcie-common`, `atc-apcie-debug`, `atc-apcie-fabric`,
     `atc-apcie-rc` and `apcie-config` tunables.
   - Waits on `acio-parent` for the ACIO's tunnel client manager and
     requires exactly one PCIe down adapter.
   - Registers the `PrtC` platform function.

   [observed]
2. **Port init** (@a02e8a8) binds the DART functions `Fact`, `Self`,
   `SReq` and `SRel` and maps the port, LTSSM, Intr2AXI and PIODMA
   blocks. [observed]
3. **Trigger.** The ACIO starts the tunnel root port.
   `AppleThunderboltPCIDownAdapterType5::pathIsEnabled(true)` (@a155220)
   runs once the host router's PCIe down adapter path is enabled. It calls
   the ACIO's `function-pcie_port_control` (`PrtC` on `apciec0`, argument
   `pcic0-bridge`). That leads to `APCIECPortControlFunction::enable(1)`
   and then `APCIECPort::enableGated`. [observed]
4. **Clocks and early tunables.** `_enableClocks` (@a02dfb0) turns on gate
   0 (AUSBn-AONPCIE-V), then gate 1 (ATCn_PCIE). It then applies the
   common, debug and fabric tunables. [observed]
5. **Port hardware.** `enablePortHardware` (@a025ef4):
   1. The T8122 `_resetPortHardware`. Compared with T8103 it writes
      0x130 = 0x03000208 and 0x124 = 0x100, never writes 0x128 or 0x810,
      and clears the 0x3800 MSI map.
   2. The `apcie-config` tunables.
   3. 0x814 |= 1 (PERST off).
   4. 0x800 |= 1, then poll 0x804 bit 0.
   5. Clear 0x800 bit 8.
   6. The RC tunables on the root port's config space.
   7. 0x4020 = 3.
   8. Intr2AXI+0x80 = 1.
   9. Rewrite RID2SID.
   10. DART `Fact`.

   [observed]
6. **Interrupts.** It writes 0x84aed00f to both 0x100 and 0x10c. Then
   `AppleT8122PCIeCPort::configMSIRange` (@a044558) writes:
   - 0x124 = 1;
   - 0x168/0x16c = the MSI address, low and high;
   - MSI map 0x3800+4·(base+i) = (base+i) | BIT(31), with base 32, 64 or
     96 for ports 0, 1 and 2.

   [observed]
7. **Start the tunnel.** It calls `startUsingTunnel()` →
   `setTunnelStart(1)`. Then `releaseResetFlow` (@a02904c) writes
   0x988 = 0 and polls 0x98c bit 0 until clear, for up to 100 ms. Finally
   it sets LTSSM enable (0x80 |= 1) and arms the `ltssm-timeout` timer.
   Link-up starts a rescan. [observed. What `setTunnelStart` does inside
   was not traced.]
8. **INTx.** INTx are not decoded from the port status register
   (`isLegacyInterrupt()` returns false). They arrive on 4 dedicated AIC
   lines and are masked through Intr2AXI+0x0 bits 3-6. [observed]

## Steps Linux lacks

They are ordered by how directly each one blocks bring-up. "Conf." gives
the confidence in what macOS does. The effect on Linux is inferred unless
the entry says otherwise.

### Bring-up blockers (ACIO start)

**1. MxWrap RUN on the T6031.** [observed, high conf.]

- **macOS:** `AppleMxWrap::_runCPU` writes 0x10 to wrapper +0x28. The
  wrapper is `acio-cpuN` reg[1], at 0xN01100000.
- **Linux:** `apple_cio_t6031_hw` has `mxwrap = false`, and the T6031
  ACIO nodes have no `cpu` reg.
- **Where:** `drivers/thunderbolt/apple.c:154-160` (hw table) and `:2639`
  (RUN). In the DT, add a `cpu` reg at 0x7/0xb/0xf_01100000 to the
  `usb4_N_acio` nodes in `t6031-dieX.dtsi:204,380,556`.

**2. Explicit LSTX on the T6031.** [observed, high conf.]

- **macOS:** writes `rc`+0x0c = 3 when a cable is connected and 2 when
  not (bit 1 = enable, bit 0 = level).
- **Linux:** the T6031 path does `rc`+0x0c |= BIT(1) (named `M3_CTRL_START`),
  which leaves the level at 0.
- **Where:** `drivers/thunderbolt/apple.c:2631-2637`. Set
  `lstx_explicit = true` for T6031.

**3. Strict firmware-ready check.** [observed, high conf.]

- **macOS:** waits until `rc`+0xa8 bits 30:24 equal 1, polling every
  5 ms.
- **Linux:** the T6031 path accepts any nonzero state.
- **Where:** `drivers/thunderbolt/apple.c:2660-2672`. Set
  `strict_fw_ready = true` for T6031.

**4. CIO reconfigure completion wait.** [observed, medium conf.]

- **macOS:** polls bit 16+n of `pmgr_cio`+0x2028 for up to 10 s, sleeping
  20 ms between reads.
- **Linux:** gives up after 100 ms, and `apple_cio_start()` then rewrites
  the request up to 5 times.
- **Where:** `drivers/reset/reset-apple-cio.c:58` (timeout) and
  `drivers/thunderbolt/apple.c:2604-2621` (retry loop).
- **Open:** whether macOS issues this request at all on the J516M. See the
  open questions.

### Tunables

**5. NHI fabric tunables land in swapped blocks.** [observed in both
sources, medium conf.]

- **macOS:** `hi_up_tx_desc` goes to NHI+0xe8000 and `hi_up_rx_desc` to
  NHI+0xf0000.
- **m1n1:** for every chip except T8142 it swaps them (0xf0000 and
  0xe8000). The T8142 table is already right.
- **Where:** m1n1 `src/kboot.c:1556-1558` (`usb4_nhi_tunables`). Nothing
  changes in Linux. The effect is unknown: the T6030 and T6021 work with
  the swap.

**6. ACIO PCIe-adapter region and tunable on the T6031.** [observed,
high conf.]

- **macOS:** applies `pcie_adapter_regs_tunables` to ACIO reg[5]
  (0xN01e44000).
- **Linux:** the T6031 ACIO nodes have no `pcie-adapter` reg, and there
  is no `usb4_N_pcie_adapter` alias for m1n1 to fill.
- **Where:** `t6031-dieX.dtsi` ACIO nodes, and the J516M board dts,
  copying the pattern of `t6030-usb4.dtsi:4-36` and
  `t603x-j514s-j516s-usb4.dtsi:4-11`.

### ATC PHY in CIO mode

**7. EQ_CDRLOCK_ON_START_EN clear.** [observed, high conf. that macOS does
it; effect unknown]

- **macOS:** clears bit 1 at LNx RX_TOP+0x1e0. That is core+0x91e0 for
  LN0 and core+0x101e0 for LN1, after the lane CIO tunables.
- **Linux:** the live J516M lane-cio tunables do not cover those
  addresses.
- **Where:** `drivers/phy/apple/atc.c`, `atcphy_apply_tunables()`, the
  USB4/TBT case (about lines 1143-1146).

**8. PHY order and delays.** [observed difference]

- **macOS:** applies AUSCMN_SHM and CLKMON_CFG after the crossbar. It
  waits 10 µs before ACIOPHY_RESET_N and 100 µs after.
- **Linux:** applies everything first, then programs the lanes, then
  releases reset with no delays.
- **Where:** `drivers/phy/apple/atc.c` `atcphy_configure()`, around lines
  3550-3570.

**9. Lane tunables and plug orientation.** [observed difference]

- **macOS:** always applies the LN0 tunables to LN0, chosen by the lane
  mask. Only the crossbar register reflects orientation.
- **Linux:** swaps the lane0 and lane1 tunables when the plug is flipped.
- **Where:** `drivers/phy/apple/atc.c:1112-1113`.

**10. ACIOPHY_LANE_USBC0 and AUX_TOP in USB4 mode.** [observed]

- **macOS:** applies these tables only in USB and DP modes.
- **Linux:** applies them in USB4 mode too, because m1n1 merges them into
  `common-b`.
- **Where:** m1n1 `kboot_atc.c` (`atc_tunables_t8122`) or `atc.c`.

### PCIe tunnel root port (T6031/T6034)

**11. No tunnel DT.** [observed]

- **macOS:** has, for every port, the PCIe-C nodes, DART, MSI window
  (AIC 1854+, not T6030's 1342), INTx lines and ranges.
- **Linux:** `t6031-dieX.dtsi` has none, and `t6034-j516m.dts` includes
  no usb4 dtsi. Only `t6030-usb4.dtsi:40-130` exists, for the T6030, and
  only for port 0.
- **Where:** a new `t6031-usb4.dtsi`, with addresses from the ADT and
  `notes-pciec.md`.

**12. MSI slice check is T6030-only.** [observed]

- **Linux:** the check is hard-coded to `apple,t6030` and AIC 1342
  (`drivers/pci/controller/pcie-apple.c:1836-1842`, `:1874-1921`).
- **Where:** make the base come from the DT.

**13. T6031 falls back to the T8103 hw.** [observed]

- **macOS:** the T8122 port requires the MSI map at 0x3800+.
- **Linux:** non-T6030 machines are downgraded to `t8103_pciec_hw`, which
  writes no MSI map.
- **Where:** `drivers/pci/controller/pcie-apple.c:3248-3253`.

**14. Reset register table is the T8103 one.** [observed; whether it
matters for link-up is inferred]

- **macOS T8122:** writes 0x130 = 0x03000208 and 0x124 = 0x100, never
  writes 0x128 or 0x810, and clears 0x3800.
- **Linux:** uses the T8103 values.
- **Where:** `drivers/pci/controller/pcie-apple.c:886-924`.

**15. `apcie-common` tunables are never applied.** [observed]

- **macOS:** applies them to reg[1] (`rc`).
- **Linux:** its tunable lists cover `rc`, `debug`, `fabric`, `oe-fabric`
  and the port only.
- **Where:** `drivers/pci/controller/pcie-apple.c:2321-2345` and
  `:3260-3283`, plus a matching m1n1 alias.

**16. MSI address high word.** [observed in macOS; likely harmless while
the doorbell is below 4 GiB]

- **macOS:** writes 0x16c.
- **Linux:** does not.
- **Where:** `drivers/pci/controller/pcie-apple.c:708-726`.

**17. INTx path.** [observed; harmless if every device uses MSI]

- **macOS:** INTx arrive on 4 dedicated AIC lines and are masked through
  Intr2AXI+0x0 bits 3-6.
- **Linux:** decodes INTx from the port status register.
- **Where:** `drivers/pci/controller/pcie-apple.c:162-163`, `:569`.

**18. Power ownership of the PCIe-C.** [observed difference]

- **macOS:** the PCIe-C owns AUSBn-AONPCIE-V and ATCn_PCIE and turns
  them on at tunnel enable.
- **Linux:** puts `ps_atcN_pcie` on the ACIO as its 4th domain and gives
  the host `ps_atcN_cio_pcie`. On the T6031 the ACIO has 3 domains, so
  `apple_cio_activate_pcie_tunnel_locked` refuses with
  "pre-ACIO PCIe-C initialization is not active".
- **Where:** `drivers/thunderbolt/apple.c:1333-1335`,
  `t6030-usb4.dtsi:10,88`.

**19. Pre-initialization gate.** [observed]

- **Linux:** accepts the T6031 only through `apple,pciec-kernel-init` or
  m1n1's preinit status. `needs_cold_init` lists only t6000/1/20/21.
- **Where:** `drivers/thunderbolt/apple.c:855-876` and
  `drivers/pci/controller/pcie-apple.c:75-77`.

### Not a gap

These match macOS already: [observed]

- PHY power-up.
- Lane mode 0 and the USB4 crossbar values.
- Skipping the common wake for USB4.
- The `rc`/`rc+0xa8` register layout.
- Applying tunables after firmware-ready.
- The CIO reconfigure register and bit layout.
- The PCIe-C tunnel reset-release poll (0x988/0x98c).

## Open questions and gaps

- **Gate index 4.** `setARMIODevicePowerState` is called for gate indices
  0, 1, 2 and 4. The ACIO `clock-gates` list has four entries (0-3), so it
  is unknown which gate index 4 means. CIO0-RECONFIG-V is index 3.
  Resolving it needs `AppleARMIODevice::setDevicePowerState` in
  AppleARMPlatform.
- **CIO reconfigure trigger on the J516M.** No
  `function-reconfig_req_interrupt` was found. So it is not shown that
  macOS ever writes `pmgr_cio`+0x2028 on this machine at runtime. A
  reconfigure may instead happen implicitly when the virtual PMGR device
  CIO0-RECONFIG-V is powered. If macOS never issues it, Linux's
  `reset_control_deassert()` in `apple_cio_start()` is an extra step
  rather than a missing one. An m1n1 hypervisor trace of macOS attaching
  a dock would settle this, and it would also give the live tunable
  values.
- **Virtual gates.** CIO0-RECONFIG-V (419) and AUSB0-AONPCIE-V (423) are
  virtual PMGR devices (flag 16, no PS register). It is not traced what
  ApplePMGR does when they are turned on, and Linux has no equivalent.
- **Firmware-ready deadline.** The poll deadline is N × 500 ms, and N
  comes from a call that was not resolved.
- **Tunable values.** The IPSW device tree has no tunable values; iBoot
  fills them. Their values, and the effect of the m1n1 tx/rx swap, need
  the live ADT. The sibling ticket `research/adt-usb4` covers the live
  values.
- **VDD_CIO across s2idle.** Not checked: whether VDD_CIO (`pmVC`) is
  turned off across s2idle by anything other than macOS's PMGR.
- **Mailbox and DART details.** The RTBuddy endpoint handshake over the
  ACIO mailbox was not traced. It is the standard RTKit boot that Linux
  already does. The DART enable/bypass policy (`enableDART`,
  `function-dart_force_active`) was not traced.
- **Teardown and sleep.** Teardown and s2idle paths (`lateSleep`,
  `earlyWake`, `doze`) were only skimmed.

Working notes and per-function listings are in
`/tmp/claude-1000/-home-ben/87888966-aece-447f-b603-cbd4008e2e02/scratchpad/kc-usb4/`
(not committed, because they contain Apple disassembly).
