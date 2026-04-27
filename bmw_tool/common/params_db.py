"""
Load extracted parameters from CSV files and build
curated "diagnostic preset" parameter sets.

Each DDE variant has hundreds of parameters in its BetriebswTab,
most of which are obscure calibration values. For a driving-dashboard
tool we need a curated subset of ~15-30 relevant sensors.

This module knows which Bosch names to pick from each DDE generation.
"""
import csv
import os
from typing import Dict, List, Optional
from .models import Parameter


# ─────────────────────────────────────────────────────────
# Dashboard parameter "templates" — what to show on display
# ─────────────────────────────────────────────────────────
#
# For each semantic concept (RPM, boost, rail pressure, ...)
# we list candidate Bosch names for DDE4 and DDE5. The first
# candidate found in the PRG wins.

DASHBOARD_TEMPLATES = {
    # key:              (label,    unit,     format,  DDE5 candidates,              DDE4 candidates)
    "rpm":              ("RPM",    "rpm",    ".0f",   ["Eng_nAvrg"],                ["MOTORDREHZAHL", "dzmNmit", "dzmNakt"]),
    "coolant_temp":     ("Coolant","°C",     ".1f",   ["CTSCD_tClntLin"],           ["MOTORTEMPERATUR", "anmWTF"]),
    "battery":          ("Batt",   "V",      ".2f",   ["BattCD_u"],                 ["anmUBT", "admUBT"]),
    "boost_actual":     ("Boost",  "hPa",    ".0f",   ["BPSCD_pOutVal", "BPSCD_pLin"], ["LADEDRUCK", "ldmP_Llin", "admLDF"]),
    "boost_target":     ("BoostT", "hPa",    ".0f",   ["PCR_pDesVal", "AirCtl_pChaDesVal"], ["ldmP_Lsoll"]),
    "atm_pressure":     ("Atm",    "hPa",    ".0f",   ["APSCD_pVal"], ["admADF"]),
    "maf":              ("MAF",    "kg/h",   ".1f",   ["AFSCD_dmAirPerTime"],       ["aroIST_4", "anmLMM"]),
    "air_per_cyl":      ("AirCyl", "mg/Hub", ".1f",   ["AFSCD_mAirPerCyl"],         ["armM_List"]),
    "air_target":       ("AirTgt", "mg/Hub", ".1f",   ["AirCtl_mDesVal"],           ["armM_Lsoll"]),
    "rail_actual":      ("Rail",   "bar",    ".0f",   ["RailCD_pPeak"],             ["RAILDRUCK", "zumP_RAIL", "admKDF"]),
    "rail_target":      ("RailTgt","bar",    ".0f",   ["Rail_pSetPoint"],           ["zumPQsoll"]),
    "fuel_q_current":   ("FuelQ",  "mg/c",   ".2f",   ["InjCtl_qCurr"],             ["mrmM_EAKT", "mrmM_EFAHR"]),
    "fuel_q_set":       ("FuelS",  "mg/c",   ".2f",   ["InjCtl_qSet"],              ["mrmM_EKORR"]),
    "fuel_temp":        ("FuelT",  "°C",     ".1f",   ["FTSCD_tFuel"],              ["anmKTF", "admKTF"]),
    "intake_temp":      ("IntT",   "°C",     ".1f",   ["IATSCD_tAir"],              ["AN_LUFTTEMPERATUR", "admLTF"]),
    "pedal":            ("Pedal",  "%",      ".1f",   ["APPCD_rFlt"],               ["PWG_FAHRERWUNSCH", "mrmPWGfi"]),
    "speed":            ("Speed",  "km/h",   ".0f",   ["PFlt_vVehFlt_mp"],          ["fgmFGAKT"]),
    "torque":           ("Torque", "Nm",     ".1f",   ["CoEng_trq"],                []),
    "torque_percent":   ("Trq%",   "%",      ".1f",   ["CoEng_rTrq"],               []),
    "cyl1_rpm":         ("Cyl1",   "rpm",    ".0f",   ["InjVlv_nCyl1"],             ["dzmzN1"]),
    "cyl2_rpm":         ("Cyl2",   "rpm",    ".0f",   ["InjVlv_nCyl2"],             ["dzmzN2"]),
    "cyl3_rpm":         ("Cyl3",   "rpm",    ".0f",   ["InjVlv_nCyl3"],             ["dzmzN3"]),
    "cyl4_rpm":         ("Cyl4",   "rpm",    ".0f",   ["InjVlv_nCyl4"],             ["dzmzN4"]),
    "cyl5_rpm":         ("Cyl5",   "rpm",    ".0f",   ["InjVlv_nCyl5"],             ["dzmzN5"]),
    "cyl6_rpm":         ("Cyl6",   "rpm",    ".0f",   ["InjVlv_nCyl6"],             ["dzmzN6"]),
}


def load_params_csv(csv_path: str) -> Dict[str, Parameter]:
    """Load all parameters from an extracted CSV into a name→Parameter dict."""
    out = {}
    with open(csv_path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            p = Parameter(
                name=row['name'],
                addr=int(row['addr'], 16),
                size=int(row['size']),
                factor_a=float(row['factor_a']),
                factor_b=float(row['factor_b']),
                unit=row['unit'],
                description=row.get('description', ''),
            )
            out[p.name] = p
    return out


def build_dashboard_params(all_params: Dict[str, Parameter]) -> List[Parameter]:
    """
    Build a curated list of dashboard parameters from the full set.
    
    For each semantic concept in DASHBOARD_TEMPLATES, try DDE5 candidates
    first, then DDE4. The first found wins. Unknown concepts are skipped.
    """
    out = []
    for key, (label, unit, fmt, dde5_cands, dde4_cands) in DASHBOARD_TEMPLATES.items():
        for name in dde5_cands + dde4_cands:
            if name in all_params:
                out.append(all_params[name])
                break
    return out


def get_params_for_sgbd(sgbd_name: str, csv_dir: str) -> Dict[str, Parameter]:
    """
    Load the parameter set for a given SGBD name ("d50m57b1", "d40m57a1", ...).
    Returns dict[name] → Parameter.
    """
    csv_path = os.path.join(csv_dir, f"{sgbd_name.lower()}.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Parameter CSV not found: {csv_path}")
    return load_params_csv(csv_path)
