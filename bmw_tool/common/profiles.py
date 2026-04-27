"""
Vehicle profiles for BMW diesel models on old K-Line bus (E39/E46/E53).
"""
from typing import List, Optional
from .models import VehicleProfile, standard_diesel_ecus


PROFILES: List[VehicleProfile] = [
    # ═════════════════════════════════════════════════════
    #                        E39
    # ═════════════════════════════════════════════════════
    VehicleProfile(
        id="e39_525tds_m51",
        name="E39 525td/525tds M51 (DDE2.x)",
        series="E39",
        engine="M51",
        dde_sgbd="",  # DDE22DS0 — not in our dataset, protocol is older
        vin_prefixes=["DF51", "DF71", "DF72", "DF81", "DF82",
                      "DG71", "DG72", "DG81", "DG82"],
        ecus=[],  # not supported: needs DDE 2.x which is pre-KWP2000
    ),
    VehicleProfile(
        id="e39_520d_m47",
        name="E39 520d M47 (DDE4)",
        series="E39",
        engine="M47",
        dde_sgbd="d40m57a1",  # FALLBACK — real d40m47* not supplied
        vin_prefixes=["DM71", "DR71"],
        ecus=standard_diesel_ecus(),
    ),
    VehicleProfile(
        id="e39_525d_530d_m57",
        name="E39 525d/530d M57 (DDE4)",
        series="E39",
        engine="M57",
        dde_sgbd="d40m57a1",  # ← DDE 4.0 for M57 E39
        vin_prefixes=[
            "DL01", "DL02", "DL91", "DL92",
            "DP01", "DP02", "DP91", "DP92",
            "DL71", "DL72", "DL81", "DL82",
            "DP71", "DP72", "DP81", "DP82",
        ],
        ecus=standard_diesel_ecus(),
    ),

    # ═════════════════════════════════════════════════════
    #                        E46
    # ═════════════════════════════════════════════════════
    VehicleProfile(
        id="e46_318d_320d_m47",
        name="E46 318d/320d M47 (DDE4, pre-LCI)",
        series="E46",
        engine="M47",
        dde_sgbd="d40m57a1",  # FALLBACK
        vin_prefixes=[
            "AL71", "AL72", "AV72", "AX71", "AX72",
            "EL51", "EU51",
        ],
        ecus=standard_diesel_ecus(),
    ),
    VehicleProfile(
        id="e46_318d_320d_m47tu",
        name="E46 318d/320d/320Cd M47TU (DDE5, LCI)",
        series="E46",
        engine="M47TU",
        dde_sgbd="d50m47b1",  # ← DDE 5.0 for M47TUE altes BN EU4
        vin_prefixes=[
            "AP71", "AP72", "AS71", "AS72",
            "AT71", "AT72", "AT91", "AZ12",
            "BS71", "BS72", "BV51", "BV52",
            "EL71", "EL72", "EU71", "EU72",
        ],
        ecus=standard_diesel_ecus(),
    ),
    VehicleProfile(
        id="e46_330d_m57",
        name="E46 330d/330xd M57 (DDE4, pre-LCI)",
        series="E46",
        engine="M57",
        dde_sgbd="d40m57a1",  # ← DDE 4.0 for M57 E46
        vin_prefixes=[
            "AL91", "AL92", "AP91", "AP92",
            "EL91", "EL92", "EP71",
            "ER91", "ER92", "ES92", "EV91",
        ],
        ecus=standard_diesel_ecus(),
    ),
    VehicleProfile(
        id="e46_330d_m57tu",
        name="E46 330d/330xd/330Cd M57TU (DDE5, LCI)",
        series="E46",
        engine="M57TU",
        dde_sgbd="d50m57a1",  # ← DDE 5.0 for M57TUE
        vin_prefixes=[
            "BV91", "BV92", "BW91", "BW92",
            "ED71", "ED91", "ED92", "EJ92",
            "EX71", "EX91", "EX92",
        ],
        ecus=standard_diesel_ecus(),
    ),

    # ═════════════════════════════════════════════════════
    #                        E53
    # ═════════════════════════════════════════════════════
    VehicleProfile(
        id="e53_x5_3.0d_m57",
        name="E53 X5 3.0d M57 (pre-LCI, 2001-2003)",
        series="E53",
        engine="M57",
        dde_sgbd="d50m57a0",  # DDE 5.0 for M57TUE early
        vin_prefixes=["FA71", "FA72"],
        ecus=standard_diesel_ecus(),
    ),
    VehicleProfile(
        id="e53_x5_3.0d_m57tu",
        name="E53 X5 3.0d M57TU (LCI, 2004-2006)",
        series="E53",
        engine="M57TU",
        dde_sgbd="d50m57b1",  # ← REFERENCE: user's test vehicle
        vin_prefixes=["FB71", "FB72"],
        ecus=standard_diesel_ecus(),
    ),
]


# ──────────────────────────────────────────────────────────
# Lookup helpers
# ──────────────────────────────────────────────────────────

def find_profile_by_typkey(typkey: str) -> Optional[VehicleProfile]:
    """Look up a profile by 4-char typkey (e.g., 'FB71')."""
    typkey = typkey.upper().strip()
    for p in PROFILES:
        if typkey in p.vin_prefixes:
            return p
    return None


def find_profile_by_vin(vin: str) -> Optional[VehicleProfile]:
    """
    Find profile from a full 17-char VIN.
    BMW VIN layout: WBA + 4-char typkey + 10-char production info
    Positions 4-7 contain the typkey (e.g., FB71 in WBAFB71090LX29041).
    """
    vin = vin.upper().strip()
    if len(vin) < 7:
        return None
    return find_profile_by_typkey(vin[3:7])


def find_profile_by_id(profile_id: str) -> Optional[VehicleProfile]:
    for p in PROFILES:
        if p.id == profile_id:
            return p
    return None


def list_profiles() -> List[VehicleProfile]:
    return list(PROFILES)


def profiles_for_sgbd(sgbd: str) -> List[VehicleProfile]:
    return [p for p in PROFILES if p.dde_sgbd == sgbd.lower()]


def count_coverage() -> dict:
    total = sum(len(p.vin_prefixes) for p in PROFILES)
    supported = sum(len(p.vin_prefixes) for p in PROFILES if p.dde_sgbd)
    return {
        'total_typkeys': total,
        'supported_typkeys': supported,
        'profiles': len(PROFILES),
        'supported_profiles': sum(1 for p in PROFILES if p.dde_sgbd),
    }


if __name__ == '__main__':
    stats = count_coverage()
    print(f"Profiles: {stats['profiles']} "
          f"({stats['supported_profiles']} supported)")
    print(f"Typkeys:  {stats['total_typkeys']} "
          f"({stats['supported_typkeys']} supported)")
    print()
    for p in PROFILES:
        marker = "✓" if p.dde_sgbd else "✗"
        print(f"  {marker} {p.id:30s}  DDE={p.dde_sgbd or '---':10s}  "
              f"{len(p.vin_prefixes):2d} typkeys")
