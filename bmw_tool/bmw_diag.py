#!/usr/bin/env python3
"""
BMW Diesel Diagnostic Tool — universal for E39/E46/E53 dieselэs on K-Line.

Workflow:
    1. Open K-Line serial port (9600 8N1 DTR=false)
    2. Wake up DDE (send A2 F8)
    3. Read AIF block from DDE → extract VIN
    4. Match VIN typkey to a vehicle profile
    5. Load curated dashboard parameters for that profile
    6. Loop: read each parameter and print live values

Usage:
    python3 bmw_diag.py --port /dev/ttyUSB0
    python3 bmw_diag.py --port COM3 --vin WBAFB71090LX29041   # skip VIN read
    python3 bmw_diag.py --list-profiles
    python3 bmw_diag.py --demo                                # no hardware
"""
import sys
import os
import time
import argparse
from typing import Optional, List

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (
    KLine,
    VehicleProfile,
    Parameter,
    find_profile_by_vin,
    find_profile_by_typkey,
    list_profiles,
    load_params_csv,
    build_dashboard_params,
    DASHBOARD_TEMPLATES,
)

# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

CSV_DIR_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "csv_params")
DDE_ADDR = 0x12


# ──────────────────────────────────────────────────────────
# Vehicle detection
# ──────────────────────────────────────────────────────────

def parse_aif_block(payload: bytes) -> Optional[dict]:
    """
    Parse the AIF (Anwender Informations Feld) response from DDE5.
    
    Input is the KWP payload after parse_kwp_ext_response, which starts
    with the positive response code 0x63 ($23 + 0x40), followed by the
    64-byte AIF block:
    
        offset 0:     0x63 = positive response to ReadMemoryByAddress
        offset 1:     0x40 marker byte
        offset 2-8:   7-char short VIN (e.g., "LX29041")
        offset 9:     space
        offset 10-12: BCD date YY MM DD (04 10 29 = 2004-10-29)
        offset 52-61: 10-char VIN prefix (e.g., "WBAFB71090")
    
    Full VIN = prefix + short.
    
    Verified on user's E53 M57TU trace:
        Payload: 63 40 4C 58 32 39 30 34 31 20 04 10 29 ... 57 42 41 46 42 37 31 30 39 30 FF FF FF
                    ^─0x40─^LX29041──────^ ^YYMMDD─^            ^WBAFB71090────────────^
    """
    if len(payload) < 62:
        return None
    if payload[0] != 0x63:  # positive response to $23
        return None
    
    try:
        vin_short = payload[2:9].decode('ascii').strip()
        if len(vin_short) != 7 or not vin_short.isalnum():
            return None
        
        vin_prefix = payload[52:62].decode('ascii').strip()
        if len(vin_prefix) != 10:
            return None
        
        full_vin = vin_prefix + vin_short
        
        # BCD date: bytes at offset 10, 11, 12
        year = payload[10]
        month = payload[11]
        day = payload[12]
        date_str = (f"20{year:02X}-{month:02X}-{day:02X}"
                    if 0 <= year < 0x50 else None)
        
        return {
            'vin': full_vin,
            'vin_short': vin_short,
            'vin_prefix': vin_prefix,
            'prog_date': date_str,
        }
    except Exception:
        return None


def parse_ident_block(payload: bytes) -> Optional[dict]:
    """
    Parse KWP2000 IDENT ($1A 80) response payload from DDE5.
    
    Input is the parsed payload from parse_kwp_ext_response, starting with
    the positive response code 0x5A:
    
        offset 0:     0x5A = positive response ($1A + 0x40)
        offset 1:     0x80 = echoed subfunction
        offset 2-7:   BMW part number (6 bytes BCD)
        offset 8:     Hardware index
        offset 9-10:  Coding index
        offset 11-12: Diagnostic index
        offset 13-14: Bus index
        offset 15:    Manufacturing week (BCD)
        offset 16:    Manufacturing year (BCD)
        offset 17:    Supplier number
        offset 18-20: Software version
        ...
    
    Verified on user's E53 trace:
        Payload: 5A 80 00 00 07 79 46 26 10 00 00 40 35 39 20 04 09 25 08 0B 01 ...
                       └─── BMW PN ───┘ HW  └CI─┘ └DI─┘ └BI─┘ KW YR SUP  SW....
                       = 00 00 07 79 46 26 BCD = 7794626
    """
    if len(payload) < 18:
        return None
    if payload[0] != 0x5A or payload[1] != 0x80:
        return None
    
    try:
        # BMW PN: 6 BCD bytes
        pn_bytes = payload[2:8]
        pn_str = ''.join(f"{(b >> 4) & 0xF}{b & 0xF}" for b in pn_bytes)
        pn_str = pn_str.lstrip('0') or '0'
        
        hw_idx = payload[8]
        coding_idx = (payload[9] << 8) | payload[10]
        diag_idx = (payload[11] << 8) | payload[12]
        
        return {
            'bmw_pn': pn_str,
            'hw_index': hw_idx,
            'coding_index': coding_idx,
            'diag_index': diag_idx,
            'raw': payload,
        }
    except Exception:
        return None


def detect_vehicle(kl: KLine) -> Optional[dict]:
    """
    Perform the full Deep OBD-style detection sequence on a DDE-equipped
    BMW diesel. Returns dict with 'vin', 'profile', etc. or None on failure.
    """
    print("[*] Waking up DDE (B8 12 F1 01 A2 F8)...")
    # Wake-up. DDE5 responds with 7F (negative) — that's OK, means "alive".
    kl.send_kwp_ext(DDE_ADDR, bytes([0xA2, 0xF8]), timeout=0.5)
    time.sleep(0.1)
    
    print("[*] Sending IDENT ($1A 80)...")
    ident_raw = kl.dde_ident(DDE_ADDR)
    if ident_raw is None:
        print("[!] No IDENT response — is DDE connected?")
        print("    Check: K-Line wiring, DTR=false, ignition ON")
        return None
    print(f"    Raw IDENT payload: {ident_raw.hex(' ')}")
    
    ident = parse_ident_block(ident_raw)
    if ident:
        print(f"    BMW PN:        {ident['bmw_pn']}")
        print(f"    HW index:      0x{ident['hw_index']:02X}")
        print(f"    Coding index:  0x{ident['coding_index']:04X}")
        print(f"    Diag index:    0x{ident['diag_index']:04X}")
    
    print("[*] Reading AIF block for VIN ($23 @ 0x000000, 0x40 bytes)...")
    aif_raw = kl.dde_read_memory(0x000000, 0x0040, DDE_ADDR)
    if aif_raw is None:
        print("[!] AIF read failed")
        return None
    print(f"    Raw AIF payload: {aif_raw[:20].hex(' ')}...")
    
    info = parse_aif_block(aif_raw)
    if info is None:
        print("[!] Could not parse VIN from AIF")
        print(f"    Full payload: {aif_raw.hex(' ')}")
        return None
    
    print(f"[✓] VIN: {info['vin']}")
    if info.get('prog_date'):
        print(f"    Programming date: {info['prog_date']}")
    
    profile = find_profile_by_vin(info['vin'])
    if profile is None:
        typkey = info['vin'][3:7] if len(info['vin']) >= 7 else '?'
        print(f"[!] No profile matches typkey '{typkey}'")
        print(f"    Available typkeys: run with --list-profiles")
        return None
    
    print(f"[✓] Profile: {profile.name}")
    info['profile'] = profile
    info['ident'] = ident
    return info


# ──────────────────────────────────────────────────────────
# Live parameter reading
# ──────────────────────────────────────────────────────────

def build_display_params(profile: VehicleProfile,
                          csv_dir: str) -> List[tuple]:
    """
    Load params for profile's DDE and return a list of
    (label, unit, display_fmt, Parameter) tuples in DASHBOARD_TEMPLATES order.
    """
    csv_path = os.path.join(csv_dir, f"{profile.dde_sgbd}.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Parameter CSV not found: {csv_path}")
    
    all_params = load_params_csv(csv_path)
    
    result = []
    for key, (label, unit, fmt, dde5_cands, dde4_cands) in DASHBOARD_TEMPLATES.items():
        chosen = None
        # DDE5 profiles use DDE5 candidates first, DDE4 second (and vice versa)
        if profile.dde_sgbd.startswith('d50'):
            candidates = dde5_cands + dde4_cands
        else:
            candidates = dde4_cands + dde5_cands
        
        for cand in candidates:
            if cand in all_params:
                chosen = all_params[cand]
                break
        
        if chosen:
            result.append((label, unit, fmt, chosen))
    
    return result


def read_param(kl: KLine, param: Parameter) -> Optional[float]:
    """Read a single parameter from DDE and convert to physical value."""
    raw = kl.dde_read_param(param.addr, param.size, DDE_ADDR)
    if raw is None or len(raw) < param.size:
        return None
    
    if param.size == 1:
        raw_int = raw[0]
    elif param.size == 2:
        raw_int = (raw[0] << 8) | raw[1]
    elif param.size == 4:
        raw_int = int.from_bytes(raw[:4], 'big')
    else:
        raw_int = int.from_bytes(raw[:param.size], 'big')
    
    return raw_int * param.factor_a + param.factor_b


def display_loop(kl: KLine, display_params: list, interval: float = 0.3):
    """
    Continuously read and display dashboard parameters.
    
    Uses batch read ($2C $10 with multiple addresses) for speed.
    DDE supports up to ~10 params per batch request.
    """
    BATCH_SIZE = 10  # max params per KWP request
    
    print()
    print("=" * 60)
    print(f"Reading {len(display_params)} parameters  (Ctrl+C to stop)")
    print("=" * 60)
    
    try:
        while True:
            values = []
            t0 = time.monotonic()
            
            # Read in batches of BATCH_SIZE
            for batch_start in range(0, len(display_params), BATCH_SIZE):
                batch = display_params[batch_start:batch_start + BATCH_SIZE]
                addrs = [p.addr for _, _, _, p in batch]
                sizes = [p.size for _, _, _, p in batch]
                
                # All params are size 2 — can use batch read
                if all(s == 2 for s in sizes):
                    raw_list = kl.dde_read_params_batch(addrs, size=2, dde_addr=DDE_ADDR)
                    if raw_list is None:
                        # Fallback to individual reads
                        raw_list = []
                        for _, _, _, p in batch:
                            raw_list.append(kl.dde_read_param(p.addr, p.size, DDE_ADDR))
                else:
                    # Mixed sizes — individual reads
                    raw_list = []
                    for _, _, _, p in batch:
                        raw_list.append(kl.dde_read_param(p.addr, p.size, DDE_ADDR))
                
                for i, (label, unit, fmt, param) in enumerate(batch):
                    raw = raw_list[i] if i < len(raw_list) else None
                    if raw is None or len(raw) < param.size:
                        values.append((label, "---", unit))
                    else:
                        raw_int = int.from_bytes(raw[:param.size], 'big')
                        phys = raw_int * param.factor_a + param.factor_b
                        values.append((label, format(phys, fmt), unit))
            
            elapsed = time.monotonic() - t0
            
            # Clear screen and print
            print(f"\033[2J\033[H", end='')
            print(f"BMW Diesel Diagnostic  —  {elapsed*1000:.0f} ms/cycle")
            print("─" * 60)
            
            # Print in 2 columns
            for i in range(0, len(values), 2):
                left = values[i]
                right = values[i+1] if i+1 < len(values) else None
                
                left_str = f"{left[0]:10s} {left[1]:>10s} {left[2]:<6s}"
                if right:
                    right_str = f"{right[0]:10s} {right[1]:>10s} {right[2]:<6s}"
                    print(f"  {left_str}    {right_str}")
                else:
                    print(f"  {left_str}")
            
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
                
    except KeyboardInterrupt:
        print("\n\n[*] Stopped by user")


# ──────────────────────────────────────────────────────────
# CLI commands
# ──────────────────────────────────────────────────────────

def cmd_diagnose(port: str, debug: bool = True):
    """
    Single-shot diagnostic test. Does each step independently with
    verbose output so the user can identify exactly where things fail.
    
    Steps:
      1. Open K-Line port
      2. Send wake-up (expect 7F negative response)
      3. Send IDENT, parse BMW PN
      4. Read AIF block, parse VIN
      5. Match profile
      6. Read ONE parameter (RPM) and decode to physical value
      7. Exit
    """
    print("=" * 60)
    print("BMW Diesel Diagnostic — single-shot test")
    print("=" * 60)
    
    # Step 1: Open port
    print(f"\n[1/6] Opening {port}...")
    try:
        kl = KLine(port, debug=debug)
    except Exception as e:
        print(f"  ✗ Failed: {type(e).__name__}: {e}")
        return
    print(f"  ✓ Port opened at 9600 8N1 DTR=false")
    
    try:
        # Step 2: Wake-up
        print(f"\n[2/6] DDE wake-up (B8 12 F1 01 A2 F8 XX)...")
        resp = kl.send_kwp_ext(DDE_ADDR, bytes([0xA2, 0xF8]), timeout=0.5)
        if resp is None:
            print("  ⚠ No response to wake-up")
            print("    This can be normal if ECU hasn't seen wake-up before")
            print("    Or it can mean: no K-Line signal, wrong pinout, engine off")
        else:
            print(f"  ✓ Response payload: {resp.hex(' ')}")
            if len(resp) >= 1 and resp[0] == 0x7F:
                print(f"    (7F = negative, but ECU is ALIVE — this is expected)")
            elif len(resp) >= 1 and resp[0] == 0x62:
                print(f"    (62 = positive response)")
        
        time.sleep(0.15)
        
        # Step 3: IDENT
        print(f"\n[3/6] IDENT ($1A 80)...")
        ident_raw = kl.dde_ident(DDE_ADDR)
        if ident_raw is None:
            print("  ✗ No IDENT response")
            print("    The DDE did not respond. Cannot continue.")
            return
        print(f"  ✓ Raw payload ({len(ident_raw)} bytes): {ident_raw.hex(' ')}")
        
        ident = parse_ident_block(ident_raw)
        if ident is None:
            print("  ⚠ Could not parse IDENT (unexpected format)")
            print(f"    First byte: 0x{ident_raw[0]:02X} (expected 0x5A)")
        else:
            print(f"    BMW PN:       {ident['bmw_pn']}")
            print(f"    HW index:     0x{ident['hw_index']:02X}")
            print(f"    Coding index: 0x{ident['coding_index']:04X}")
            print(f"    Diag index:   0x{ident['diag_index']:04X}")
        
        # Step 4: AIF / VIN
        print(f"\n[4/6] Read AIF for VIN ($23 @ 0x000000, 0x0040)...")
        aif_raw = kl.dde_read_memory(0x000000, 0x0040, DDE_ADDR)
        if aif_raw is None:
            print("  ✗ AIF read failed")
            return
        print(f"  ✓ Raw payload ({len(aif_raw)} bytes)")
        
        info = parse_aif_block(aif_raw)
        if info is None:
            print("  ✗ Could not parse AIF")
            print(f"    Full payload: {aif_raw.hex(' ')}")
            return
        print(f"    VIN:          {info['vin']}")
        print(f"    Prog date:    {info.get('prog_date', 'unknown')}")
        
        # Step 5: Profile match
        print(f"\n[5/6] Match profile...")
        profile = find_profile_by_vin(info['vin'])
        if profile is None:
            print(f"  ✗ No profile for typkey {info['vin'][3:7]}")
            return
        print(f"  ✓ Profile: {profile.name}")
        print(f"    DDE SGBD: {profile.dde_sgbd}")
        
        # Step 6: Read ONE parameter (RPM)
        print(f"\n[6/6] Read ONE parameter (RPM)...")
        csv_dir = CSV_DIR_DEFAULT
        try:
            display_params = build_display_params(profile, csv_dir)
        except FileNotFoundError as e:
            print(f"  ✗ Parameter CSV missing: {e}")
            return
        
        # Find RPM
        rpm_entry = None
        for label, unit, fmt, p in display_params:
            if label == 'RPM':
                rpm_entry = (label, unit, fmt, p)
                break
        
        if rpm_entry is None:
            print("  ✗ No RPM parameter in profile")
            return
        
        _, unit, fmt, param = rpm_entry
        print(f"  Reading {param.name} @ 0x{param.addr:04X} size={param.size}")
        print(f"  Request: $2C $10 {(param.addr >> 8):02X} {(param.addr & 0xFF):02X}")
        
        raw = kl.dde_read_param(param.addr, param.size, DDE_ADDR)
        if raw is None:
            print("  ✗ Parameter read failed")
            return
        
        print(f"  ✓ Raw bytes: {raw.hex(' ')}")
        
        # Decode to physical
        if param.size == 2:
            raw_int = (raw[0] << 8) | raw[1]
        elif param.size == 1:
            raw_int = raw[0]
        else:
            raw_int = int.from_bytes(raw[:param.size], 'big')
        
        phys = raw_int * param.factor_a + param.factor_b
        print(f"  ✓ Raw value:      {raw_int}")
        print(f"  ✓ Scale:          {raw_int} × {param.factor_a} + {param.factor_b}")
        print(f"  ✓ Physical value: {phys:{fmt}} {unit}")
        
        if 'RPM' in unit.upper() or 'rpm' in param.unit:
            if 400 < phys < 6000:
                print(f"    → Engine is RUNNING ({phys:.0f} rpm)")
            elif phys < 10:
                print(f"    → Engine is OFF (0 rpm)")
            else:
                print(f"    → Unusual value, check scaling")
        
        print(f"\n{'='*60}")
        print("✓ All steps completed successfully")
        print(f"{'='*60}")
        print(f"\nNext step: run 'python3 bmw_diag.py --port {port}' for live loop")
        
    except Exception as e:
        print(f"\n[!] Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        kl.close()


def cmd_list_profiles():
    """Print all known vehicle profiles."""
    profiles = list_profiles()
    print(f"Known profiles: {len(profiles)}\n")
    for p in profiles:
        marker = "✓" if p.dde_sgbd else "✗"
        supported = f"{len(p.vin_prefixes):2d} typkeys"
        print(f"  {marker} {p.id:30s}  {p.name}")
        print(f"      DDE: {p.dde_sgbd or '(not supported)':15s}  {supported}")
        if p.vin_prefixes:
            keys = ' '.join(p.vin_prefixes[:8])
            if len(p.vin_prefixes) > 8:
                keys += f" ... (+{len(p.vin_prefixes)-8} more)"
            print(f"      Keys: {keys}")
        print()


def cmd_demo(csv_dir: str, vin: str):
    """Dry-run: show what parameters would be displayed for a given VIN."""
    profile = find_profile_by_vin(vin)
    if profile is None:
        print(f"[!] No profile for VIN {vin} (typkey {vin[3:7]})")
        return
    
    print(f"VIN:     {vin}")
    print(f"Typkey:  {vin[3:7]}")
    print(f"Profile: {profile.name}")
    print(f"DDE:     {profile.dde_sgbd}")
    print()
    
    try:
        display_params = build_display_params(profile, csv_dir)
    except FileNotFoundError as e:
        print(f"[!] {e}")
        return
    
    print(f"Dashboard parameters ({len(display_params)}):")
    print(f"  {'Label':12s} {'Addr':7s} {'Name':30s} {'Scale':>10s} {'Unit':6s}")
    print("  " + "─" * 70)
    for label, unit, fmt, p in display_params:
        scale = f"{p.factor_a:.4g}"
        print(f"  {label:12s} 0x{p.addr:04X}  {p.name:30s} {scale:>10s} {p.unit:6s}")


def cmd_live(port: str, csv_dir: str, vin_override: Optional[str] = None,
             debug: bool = False):
    """Connect to car and read live parameters."""
    print(f"[*] Opening {port}...")
    try:
        with KLine(port, debug=debug) as kl:
            
            if vin_override:
                print(f"[*] Using supplied VIN: {vin_override}")
                profile = find_profile_by_vin(vin_override)
                if profile is None:
                    print(f"[!] No profile for VIN {vin_override}")
                    return
                print(f"[✓] Profile: {profile.name}")
                # Still wake up DDE for parameter reads
                kl.send_kwp_ext(DDE_ADDR, bytes([0xA2, 0xF8]), timeout=0.5)
                time.sleep(0.1)
            else:
                info = detect_vehicle(kl)
                if info is None:
                    return
                profile = info['profile']
            
            print(f"[*] Loading parameters for {profile.dde_sgbd}...")
            display_params = build_display_params(profile, csv_dir)
            print(f"[✓] Loaded {len(display_params)} dashboard parameters")
            
            display_loop(kl, display_params, interval=0.5)
            
    except Exception as e:
        print(f"[!] {type(e).__name__}: {e}")
        if debug:
            import traceback
            traceback.print_exc()


# ──────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="BMW Diesel Diagnostic Tool (E39/E46/E53)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument('--port', help='Serial port (e.g. /dev/ttyUSB0 or COM3)')
    ap.add_argument('--vin', help='Override VIN (skip detection)')
    ap.add_argument('--csv-dir', default=CSV_DIR_DEFAULT,
                    help=f'Directory with extracted CSVs (default: {CSV_DIR_DEFAULT})')
    ap.add_argument('--list-profiles', action='store_true',
                    help='List all known vehicle profiles and exit')
    ap.add_argument('--demo', action='store_true',
                    help='Dry-run: show params for --vin without connecting')
    ap.add_argument('--diagnose', action='store_true',
                    help='Single-shot test: wake + IDENT + AIF + 1 param read, then exit')
    ap.add_argument('--debug', action='store_true',
                    help='Print TX/RX bytes')
    args = ap.parse_args()
    
    if args.list_profiles:
        cmd_list_profiles()
        return
    
    if args.demo:
        vin = args.vin or 'WBAFB71090LX29041'  # default to user's car
        cmd_demo(args.csv_dir, vin)
        return
    
    if args.diagnose:
        if not args.port:
            ap.error("--diagnose requires --port")
        cmd_diagnose(args.port, debug=True)  # diagnose is always verbose
        return
    
    if not args.port:
        ap.error("--port is required for live operation (or use --demo / --list-profiles / --diagnose)")
    
    cmd_live(args.port, args.csv_dir, args.vin, args.debug)


if __name__ == '__main__':
    main()
