# BMW Diesel Diagnostic Tool

Universal diagnostic tool for old K-Line BMW diesels: **E39, E46, E53**.

Supports engines: **M47, M47TU, M57, M57TU** via DDE4 and DDE5.

## Coverage

9 profiles, 76 BMW type keys (typkeys), 67 fully supported:

| Series | Engine | DDE | Typkeys | PRG file |
|---|---|---|---|---|
| E39 | M51 (525tds) | DDE2.x | 9 | ✗ not supported |
| E39 | M47 (520d) | DDE4 | 2 | ⚠ fallback to d40m57a1 |
| E39 | M57 (525d/530d) | DDE4 | 16 | ✓ d40m57a1 |
| E46 | M47 (318d/320d early) | DDE4 | 7 | ⚠ fallback |
| E46 | M47TU (318d/320d LCI) | DDE5 | 16 | ✓ d50m47b1 |
| E46 | M57 (330d early) | DDE4 | 11 | ✓ d40m57a1 |
| E46 | M57TU (330d LCI) | DDE5 | 11 | ✓ d50m57a1 |
| E53 | M57 (X5 3.0d 2001-2003) | DDE5 | 2 | ✓ d50m57a0 |
| E53 | M57TU (X5 3.0d LCI 2004-2006) | DDE5 | 2 | ✓ d50m57b1 **← reference** |

## ⭐ Start here: --diagnose

**First time on a car, run this:**

```bash
python3 bmw_diag.py --port /dev/ttyUSB0 --diagnose
```

This runs a single-shot test that will tell you EXACTLY where things
fail (if they do):

```
============================================================
BMW Diesel Diagnostic — single-shot test
============================================================

[1/6] Opening /dev/ttyUSB0...
  ✓ Port opened at 9600 8N1 DTR=false

[2/6] DDE wake-up (B8 12 F1 01 A2 F8 XX)...
  TX: b8 12 f1 01 a2 f8
  RX: b8 f1 12 03 7f a2 11 94
  ✓ Response payload: 7f a2 11
    (7F = negative, but ECU is ALIVE — this is expected)

[3/6] IDENT ($1A 80)...
  TX: b8 12 f1 02 1a 80 c3
  RX: b8 f1 12 1f 5a 80 00 00 07 79 46 26 10 ...
  ✓ Raw payload (31 bytes): 5a 80 00 00 07 79 46 26 10 ...
    BMW PN:       7794626
    HW index:     0x10
    Coding index: 0x0000
    Diag index:   0x4035

[4/6] Read AIF for VIN ($23 @ 0x000000, 0x0040)...
  ✓ Raw payload (65 bytes)
    VIN:          WBAFB71090LX29041
    Prog date:    2004-10-29

[5/6] Match profile...
  ✓ Profile: E53 X5 3.0d M57TU (LCI, 2004-2006)
    DDE SGBD: d50m57b1

[6/6] Read ONE parameter (RPM)...
  Reading Eng_nAvrg @ 0x0091 size=2
  Request: $2C $10 00 91
  ✓ Raw bytes: 00 00
  ✓ Raw value:      0
  ✓ Scale:          0 × 0.125002 + 0.0
  ✓ Physical value: 0 rpm
    → Engine is OFF (0 rpm)

============================================================
✓ All steps completed successfully
============================================================
```

If any step fails, send me the output and I'll know exactly where the
issue is.

## Usage

```bash
# List all known profiles
python3 bmw_diag.py --list-profiles

# Dry-run: show params for a VIN without connecting (no hardware needed)
python3 bmw_diag.py --demo --vin WBAFB71090LX29041

# ⭐ Single-shot diagnose (recommended FIRST)
python3 bmw_diag.py --port /dev/ttyUSB0 --diagnose

# Live parameter loop
python3 bmw_diag.py --port /dev/ttyUSB0
python3 bmw_diag.py --port COM3 --debug        # with TX/RX logging
python3 bmw_diag.py --port /dev/ttyUSB0 --vin WBAFB71090LX29041  # skip VIN read
```

## Protocol Facts (verified from init.trc / ifh.trc)

**One physical layer** for all old BMW diesels:
- K-Line, **9600 baud, 8N1, DTR=false**, half-duplex with local echo

**Two frame formats** on the same bus:
- **KWP2000 ext (B8 header)** for DDE (0x12) and EGS (0x18):
  `[B8][DST][F1][LEN][DATA][XOR_CS]`
- **DS2 classic** for IKE (0x80), EWS3 (0x44), LCM (0xD0):
  `[ADDR][LEN][DATA][XOR_CS]`

**CRITICAL: Both formats use XOR checksum, not ADD.** Verified on 4 real
frames from user's E53 — ADD gives 0/4 matches, XOR gives 4/4:

| Frame | Expected CS | ADD | XOR |
|---|---|---|---|
| `B8 12 F1 01 A2` | F8 | 5E ✗ | **F8 ✓** |
| `B8 12 F1 02 1A 80` | C3 | 57 ✗ | **C3 ✓** |
| `B8 12 F1 06 23 00 00 00 07 40` | 39 | 2B ✗ | **39 ✓** |
| `B8 12 F1 06 23 00 00 40 07 40` | 79 | 6B ✗ | **79 ✓** |

### DDE5 wake-up

```
TX: B8 12 F1 01 A2 F8 5C   ← wake
RX: B8 F1 12 03 7F A2 11 94  ← negative response, but ECU alive
```

The ECU returns a 7F (negative) on wake-up. This is **normal**, not
an error — the ECU just woke up and is now responding to subsequent
requests.

### IDENT ($1A 80)

```
TX: B8 12 F1 02 1A 80 C3
RX: B8 F1 12 1F 5A 80 00 00 07 79 46 26 10 ... 7F
           └payload──┘
                    └─── BMW PN ───┘ HW ...
```

### Read VIN from AIF ($23 ReadMemoryByAddress)

```
TX: B8 12 F1 06 23 00 00 00 07 40 39
                   └─addr─┘ └len─┘
                   0x000000  0x0740 → read 64 bytes from address 0
RX: B8 F1 12 41 63 40 4C 58 32 39 30 34 31 ... 8F
             └─┘└┘└── "LX29041" ─────┘
              │ marker
              positive response ($23 + 0x40 = 0x63)
```

AIF layout in payload (after positive response code 0x63):
- offset 1: 0x40 marker byte
- offset 2-8: 7-char short VIN (e.g., "LX29041")
- offset 10-12: BCD date YY MM DD (programming date)
- offset 52-61: 10-char VIN prefix (e.g., "WBAFB71090")
- **Full VIN = prefix + short**

### Read parameter ($2C $10 ReadDataByLocalID)

```
TX: B8 12 F1 04 2C 10 00 6E 0D   ← read APSCD_pVal (addr 0x006E)
                └┬┘ └┬┘ └──┘
                 │  10  DDE memory address (16-bit)
                 ReadDataByLocalID
RX: B8 F1 12 04 6C 10 1F 87 BB
              └─┘└─┘└──┘
               │  10  2 bytes raw data = 0x1F87 = 8071
               positive resp ($2C + 0x40)
```

Scaling: 8071 × 0.125002 + 0 = **1008.89 hPa** (atmospheric pressure)

**IMPORTANT:** The response does NOT echo the address. After parsing
the KWP header, the payload layout is just `[6C][10][DATA...]`, so
data starts at offset 2, not 4.

### VIN → typkey → profile

BMW VIN positions 4-7 contain the 4-character typkey directly:
```
WBAFB71090LX29041
   ^^^^
   FB71  →  E53 X5 3.0d M57TU LCI  →  d50m57b1.prg
```

## Dashboard parameters (up to 25 values)

| Label | Description | DDE5 name | DDE4 name |
|---|---|---|---|
| RPM | Engine speed | Eng_nAvrg | MOTORDREHZAHL |
| Coolant | Coolant temp | CTSCD_tClntLin | MOTORTEMPERATUR |
| Batt | Battery voltage | BattCD_u | admUBT |
| Boost | Actual boost | **BPSCD_pOutVal** | LADEDRUCK |
| BoostT | Target boost | **PCR_pDesVal** | ldmP_Lsoll |
| Atm | Atmospheric | **APSCD_pVal** | admADF |
| MAF | Air mass flow | AFSCD_dmAirPerTime | aroIST_4 |
| AirCyl | Air per cylinder | AFSCD_mAirPerCyl | armM_List |
| AirTgt | Target air | AirCtl_mDesVal | armM_Lsoll |
| Rail | Rail pressure | RailCD_pPeak | RAILDRUCK |
| RailTgt | Target rail | Rail_pSetPoint | zumPQsoll |
| FuelQ | Fuel qty current | InjCtl_qCurr | mrmM_EAKT |
| FuelS | Fuel qty set | InjCtl_qSet | mrmM_EKORR |
| FuelT | Fuel temp | FTSCD_tFuel | anmKTF |
| IntT | Intake air temp | IATSCD_tAir | AN_LUFTTEMPERATUR |
| Pedal | Pedal position | APPCD_rFlt | PWG_FAHRERWUNSCH |
| Speed | Vehicle speed | PFlt_vVehFlt_mp | fgmFGAKT |
| Torque | Engine torque | CoEng_trq | — |
| Trq% | Torque % | CoEng_rTrq | — |
| Cyl1..Cyl6 | Per-cylinder RPM | InjVlv_nCyl1..6 | dzmzN1..N6 |

**Important correction from earlier work:** BPSCD and APSCD are NOT swapped.
- `BPSCD_pOutVal` = Ladedruckwert = **boost pressure (actual)**
- `APSCD_pVal` = Atmosphärendruck = **atmospheric pressure**
- `PCR_pDesVal` = Ladedrucksollwert = **boost pressure (target)**

## Project structure

```
bmw_tool/
├── bmw_diag.py              Main script — connect, detect, read live
├── extractors/
│   ├── extract_params.py    Universal DDE4/DDE5 BetriebswTab extractor
│   └── check_coverage.py    Verify dashboard template coverage
├── common/
│   ├── models.py            Protocol enum, Parameter, EcuConfig, VehicleProfile
│   ├── kline.py             K-Line transport (KWP ext B8 + DS2 classic)
│   ├── profiles.py          9 vehicle profiles for E39/E46/E53 diesels
│   ├── vin_matcher.py       67 diesel typkeys, VIN → profile lookup
│   ├── params_db.py         DASHBOARD_TEMPLATES + CSV loaders
│   ├── data/                JSON reference data (typkeys)
│   └── __init__.py          Public API
└── csv_params/
    ├── d50m57b1.csv         377 params — E53 X5 3.0d LCI (user's car)
    ├── d50m57a1.csv         213 params — E46 330d LCI / E53 early
    ├── d50m57a0.csv         216 params — E46/E53 early
    ├── d50m47b1.csv         377 params — E46 320d LCI
    ├── d50m47a0.csv         207 params — E46 320d early DDE5
    └── d40m57a1.csv         160 params — E39/E46 M57 DDE4
```

## Hardware

Any K-DCAN/K-Line USB adapter (FTDI FT232R-based) should work. OBD-II pins:
- Pin 7: K-Line
- Pin 5: Signal ground
- Pin 16: 12V (not used, powered by car)

**Critical:** Set DTR=false (low) on your USB adapter. With DTR high,
the K-Line idle state is wrong and no ECU will respond. The tool does
this automatically via pyserial.

## What has been verified on real trace data

All parsing logic has been tested against actual traffic captured from
the reference vehicle (WBAFB71090LX29041):

✅ `cs_xor` — matches on all 4 sample frames
✅ `parse_kwp_ext_response` — recovers correct payload from IDENT, AIF, param read
✅ `parse_ident_block` — extracts BMW PN "7794626" from real IDENT response
✅ `parse_aif_block` — extracts VIN "WBAFB71090LX29041" and date "2004-10-29"
✅ `dde_read_param` — decodes all 5 sample parameter reads correctly:
   - RPM: 0 (engine off)
   - Atmospheric: 1008.89 hPa
   - Boost actual: 1011.89 hPa (= atm, engine off)
   - Rail actual: 2.08 bar (residual)
   - Rail target: 379.49 bar (idle target)

**Not yet verified (depends on hardware):**
- Timing constants P1..P4 for K-Line on your specific USB adapter
- Echo consumption on half-duplex line
- Wake-up sequence behavior across ignition cycles

If `--diagnose` shows a problem, send me the output and I can fix it.

## Known limitations

1. **M47 DDE4** — we only have `d40m57a1.prg` (for M57). M47 parameter
   addresses and names differ slightly. Marked as fallback in profiles.

2. **E39 M51 (525tds)** — uses DDE2.x pre-KWP2000 protocol. Out of scope.

3. **Grpliste bit-rules not implemented** — static ECU list per profile.

4. **No D-CAN / UDS support** — E60/E90 need a different transport.
