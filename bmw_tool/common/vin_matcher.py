"""
VIN matcher for BMW old diesel vehicles (E39, E46, E53).

BMW stores the Typenschlüssel (4-character type key) directly in VIN
positions 4-7. For example:

    WBAFB71090LX29041
       ^^^^             = Typenschlüssel "FB71" = X5 3.0d M57TU LCI

This module provides a lookup from typkey → (series, engine, description)
for all 67 diesel variants on old BMW chassis (pre-E60).
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class VinInfo:
    """Information about a vehicle extracted from its VIN."""
    vin: str
    typkey: str              # 4-char BMW Typenschlüssel
    series: str              # "E39", "E46", "E53"
    engine: str              # "M47", "M47TU", "M57", "M57TU"
    description: str         # human-readable "330d M57TU LCI"
    is_diesel: bool = True


# ───────── Diesel typkey → profile mapping ─────────
# Extracted from FZGIDENT.prg (EDIABAS v67.1 SP-DATEN)
# Format: typkey → (series, engine, description)

DIESEL_TYPKEYS = {
    # ══════════════════════ E39 ══════════════════════
    # M47 (520d — DDE4)
    'DM71': ('E39', 'M47',   '520d M LIM'),
    'DR71': ('E39', 'M47',   '520d M TOUR'),
    # M57 (525d, 530d — DDE4)
    'DL01': ('E39', 'M57',   '525d A LIM'),
    'DL02': ('E39', 'M57',   '525d A LIM'),
    'DL71': ('E39', 'M57',   '530d M LIM'),
    'DL72': ('E39', 'M57',   '530d M LIM'),
    'DL81': ('E39', 'M57',   '530d A LIM'),
    'DL82': ('E39', 'M57',   '530d A LIM'),
    'DL91': ('E39', 'M57',   '525d M LIM'),
    'DL92': ('E39', 'M57',   '525d M LIM'),
    'DP01': ('E39', 'M57',   '525d A TOUR'),
    'DP02': ('E39', 'M57',   '525d A TOUR'),
    'DP71': ('E39', 'M57',   '530d M TOUR'),
    'DP72': ('E39', 'M57',   '530d M TOUR'),
    'DP81': ('E39', 'M57',   '530d A TOUR'),
    'DP82': ('E39', 'M57',   '530d A TOUR'),
    'DP91': ('E39', 'M57',   '525d M TOUR'),
    'DP92': ('E39', 'M57',   '525d M TOUR'),

    # ══════════════════════ E46 ══════════════════════
    # M47 pre-LCI (318d, 320d — DDE4)
    'AL71': ('E46', 'M47',   '320d LIM'),
    'AL72': ('E46', 'M47',   '320d LIM'),
    'AV72': ('E46', 'M47',   '320d LIM'),
    'AX71': ('E46', 'M47',   '320d TOUR'),
    'AX72': ('E46', 'M47',   '320d TOUR'),
    'EL51': ('E46', 'M47',   '318d TOUR'),
    'EU51': ('E46', 'M47',   '318d LIM'),
    # M47TU LCI (318d/320d/320Cd — DDE5)
    'AP71': ('E46', 'M47TU', '320d TOUR LCI'),
    'AP72': ('E46', 'M47TU', '320d TOUR LCI'),
    'AS71': ('E46', 'M47TU', '320d LIM LCI'),
    'AS72': ('E46', 'M47TU', '320d LIM LCI'),
    'AT71': ('E46', 'M47TU', '320td COMPACT'),
    'AT72': ('E46', 'M47TU', '320td COMPACT'),
    'AT91': ('E46', 'M47TU', '318td COMPACT'),
    'AZ12': ('E46', 'M47TU', '320d LIM'),
    'BS71': ('E46', 'M47TU', '320Cd CABRIO'),
    'BS72': ('E46', 'M47TU', '320Cd CABRIO'),
    'BV51': ('E46', 'M47TU', '320Cd COUPE'),
    'BV52': ('E46', 'M47TU', '320Cd COUPE'),
    'EL71': ('E46', 'M47TU', '318d TOUR'),
    'EL72': ('E46', 'M47TU', '318d TOUR'),
    'EU71': ('E46', 'M47TU', '318d LIM'),
    'EU72': ('E46', 'M47TU', '318d LIM'),
    # M57 pre-LCI (330d — DDE4)
    'AL91': ('E46', 'M57',   '330d LIM'),
    'AL92': ('E46', 'M57',   '330d LIM'),
    'AP91': ('E46', 'M57',   '330d TOUR'),
    'AP92': ('E46', 'M57',   '330d TOUR'),
    'EL91': ('E46', 'M57',   '330d TOUR'),
    'EL92': ('E46', 'M57',   '330d TOUR'),
    'EP71': ('E46', 'M57',   '330xd TOUR'),
    'ER91': ('E46', 'M57',   '330d LIM'),
    'ER92': ('E46', 'M57',   '330d LIM'),
    'ES92': ('E46', 'M57',   '330d LIM'),
    'EV91': ('E46', 'M57',   '330xd LIM'),
    # M57TU LCI (330d/330xd/330Cd — DDE5)
    'BV91': ('E46', 'M57TU', '330Cd COUPE'),
    'BV92': ('E46', 'M57TU', '330Cd COUPE'),
    'BW91': ('E46', 'M57TU', '330Cd CABRIO'),
    'BW92': ('E46', 'M57TU', '330Cd CABRIO'),
    'ED71': ('E46', 'M57TU', '330xd LIM LCI'),
    'ED91': ('E46', 'M57TU', '330d LIM LCI'),
    'ED92': ('E46', 'M57TU', '330d LIM LCI'),
    'EJ92': ('E46', 'M57TU', '330d LIM LCI'),
    'EX71': ('E46', 'M57TU', '330xd TOUR LCI'),
    'EX91': ('E46', 'M57TU', '330d TOUR LCI'),
    'EX92': ('E46', 'M57TU', '330d TOUR LCI'),

    # ══════════════════════ E53 ══════════════════════
    # M57 pre-LCI (2001-2003 X5 3.0d)
    'FA71': ('E53', 'M57',   'X5 3.0d'),
    'FA72': ('E53', 'M57',   'X5 3.0d'),
    # M57TU LCI (2004-2006 X5 3.0d) ← the user's car
    'FB71': ('E53', 'M57TU', 'X5 3.0d LCI'),
    'FB72': ('E53', 'M57TU', 'X5 3.0d LCI'),
}


# BMW WMI (first 3 chars of VIN) — helps validate that this is a BMW
BMW_WMI = {'WBA', 'WBS', 'WBX', 'WBY', '4US', '5UX', '5UM'}


def parse_vin(vin: str) -> Optional[VinInfo]:
    """
    Parse a BMW VIN and return VinInfo for known diesel variants.
    Returns None if the VIN is not recognized as a supported diesel.
    
    BMW VIN layout (17 chars):
        positions 1-3:  World Manufacturer Identifier (WBA, WBS, WBX, ...)
        positions 4-7:  BMW Typenschlüssel (4 chars)         ← key field
        position 8:     check digit / restraint info
        position 9:     check digit
        position 10:    model year (older BMWs: position in production)
        position 11:    plant code
        positions 12-17: sequential production number
    """
    if not vin or len(vin) != 17:
        return None
    vin = vin.upper().strip()
    
    wmi = vin[0:3]
    typkey = vin[3:7]
    
    if typkey not in DIESEL_TYPKEYS:
        return None
    
    series, engine, desc = DIESEL_TYPKEYS[typkey]
    
    # Build full description with WMI prefix if unusual
    if wmi not in BMW_WMI:
        desc = f"[WMI {wmi}] {desc}"
    
    return VinInfo(
        vin=vin,
        typkey=typkey,
        series=series,
        engine=engine,
        description=desc,
        is_diesel=True,
    )


def profile_key_for_vin(vin: str) -> Optional[str]:
    """
    Given a VIN, return the profile identifier string for loading,
    e.g., "e53_m57tu" or "e46_m47" or None if not supported.
    """
    info = parse_vin(vin)
    if info is None:
        return None
    return f"{info.series.lower()}_{info.engine.lower()}"


def profile_key_for_typkey(typkey: str) -> Optional[str]:
    """Resolve a typkey directly (bypass VIN parsing) to profile key."""
    typkey = typkey.upper()
    if typkey not in DIESEL_TYPKEYS:
        return None
    series, engine, _ = DIESEL_TYPKEYS[typkey]
    return f"{series.lower()}_{engine.lower()}"


if __name__ == '__main__':
    # Self-test
    test_vins = [
        ('WBAFB71090LX29041', 'e53_m57tu'),   # user's car
        ('WBAAL92040XX00001', 'e46_m57'),     # E46 330d early (made up serial)
        ('WBAED91060YY11111', 'e46_m57tu'),   # E46 330d LCI
        ('WBADL71050ZZ22222', 'e39_m57'),     # E39 530d
        ('WBADR71020AA33333', 'e39_m47'),     # E39 520d
        ('WBAAS72070BB44444', 'e46_m47tu'),   # E46 320d LCI
        ('WBAEL51040CC55555', 'e46_m47'),     # E46 318d early
        ('WBAFA71010DD66666', 'e53_m57'),     # E53 X5 3.0d pre-LCI
        ('WBAXXXX000XX00000', None),          # unknown typkey
        ('ABCDEFGHIJKLMNOPQ', None),          # not a BMW
        ('SHORT', None),                      # wrong length
    ]
    print(f"Supported diesel typkeys: {len(DIESEL_TYPKEYS)}\n")
    for vin, expected in test_vins:
        result = profile_key_for_vin(vin)
        info = parse_vin(vin)
        mark = "✓" if result == expected else "✗"
        info_str = f"{info.series} {info.engine:6s} {info.description}" if info else "---"
        print(f"  {mark} {vin}  →  {str(result):12s}  [{info_str}]")
