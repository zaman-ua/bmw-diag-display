"""
BMW DDE Parameter Database
===========================
Auto-extracted from PRG files by reverse-engineering BEST1 bytecode.

Contains ECU memory addresses and conversion formulas for KWP2000
$2C DefineDataByLocalIdentifier service.

Usage:
    from dde_params_db import get_params_for_ecu
    params = get_params_for_ecu('d50m57b1')  # E53 X5 3.0d DDE5
    for p in params:
        print(f"{p['name']:30s} ADR=0x{p['adr']:04X} {p['unit']}")

Supported ECUs:
    d40m57a1  - DDE4 M57 (E39 530d early)
    d50m57a0  - DDE5 M57TU (E39/E46 530d/330d)
    d50m57b1  - DDE5 M57TU (E53 X5 3.0d)
    d50m57c0  - DDE5 M57TU (E60 530d pre-facelift)
    d50m57d0  - DDE5 M57TU (E60 530d EU4)
    d60m57a0  - DDE6 M57TU2 (E60/E90 LCI 530d/325d)
    d62m57a0  - DDE6.2 M57TU2TOP (E60 535d bi-turbo)
    d62m57b0  - DDE6.2 M57TU2 (E60/E90 530d LCI)
    d50m47a   - DDE5 M47TU (E46 320d)
    d50m47b1  - DDE5 M47TU (E46/E83 320d EU4)
    d60m47a0  - DDE6 M47TU2 (E90 320d)

Protocol: KWP2000 over K-Line (DDE4/DDE5) or BMW-FAST over D-CAN (DDE6+)
    Telegram: B8 12 F1 04 2C 10 [ADR_H] [ADR_L]
    Read:     83 12 F1 21 10  ->  response: 83 F1 12 61 10 [DATA_H] [DATA_L]
    Formula:  physical_value = raw_uint16 * fact_a + fact_b
"""

# Key parameters with ADR for each ECU variant
# Format: { bosch_name: { ecu_file: (adr, fact_a, fact_b, unit) } }

PARAM_DB = {
    # ==================== ENGINE ====================
    "Eng_nAvrg": {
        "description": "Engine RPM (averaged)",
        "d50m57a0": (0x002D, 0.125002, 0.0, "rpm"),
        "d50m57b1": (0x0091, 0.125002, 0.0, "rpm"),
        "d50m57c0": (0x002D, 0.125002, 0.0, "rpm"),
        "d50m57d0": (0x002D, 0.125002, 0.0, "rpm"),
        "d60m57a0": (0x009E, 0.125002, 0.0, "rpm"),
        "d62m57a0": (0x009E, 0.125002, 0.0, "rpm"),
        "d62m57b0": (0x009E, 0.125002, 0.0, "rpm"),
        "d50m47a":  (0x002D, 0.125002, 0.0, "rpm"),
        "d50m47b1": (0x0091, 0.125002, 0.0, "rpm"),
        "d60m47a0": (0x009E, 0.125002, 0.0, "rpm"),
    },
    "Eng_nAvrg_Carb": {
        "description": "Engine RPM (carburetor method)",
        "d50m57a0": (0x000C, 0.250000, 0.0, "rpm"),
        "d50m57b1": (0x000C, 0.250000, 0.0, "rpm"),
        "d50m57c0": (0x000C, 0.250000, 0.0, "rpm"),
        "d60m57a0": (0x000C, 0.250000, 0.0, "rpm"),
        "d50m47a":  (0x000C, 0.250000, 0.0, "rpm"),
        "d50m47b1": (0x000C, 0.250000, 0.0, "rpm"),
        "d60m47a0": (0x000C, 0.250000, 0.0, "rpm"),
    },

    # ==================== TEMPERATURE ====================
    "CTSCD_tClntLin": {
        "description": "Coolant temperature (linearized)",
        "d50m57a0": (0x0005, 1.000240, -41.084, "°C"),
        "d50m57b1": (0x0005, 1.000240, -41.084, "°C"),
        "d50m57c0": (0x0005, 1.000240, -41.084, "°C"),
        "d60m57a0": (0x0005, 1.000240, -41.084, "°C"),
        "d62m57a0": (0x0005, 1.000240, -41.084, "°C"),
        "d50m47a":  (0x0005, 1.000240, -41.084, "°C"),
        "d50m47b1": (0x0005, 1.000240, -41.084, "°C"),
        "d60m47a0": (0x0005, 1.000240, -41.084, "°C"),
    },
    "IATSCD_tAir": {
        "description": "Intake air temperature",
        "d50m57a0": (0x0038, 0.016787, -50.138, "°C"),
        "d50m57b1": (0x009C, 0.016787, -50.138, "°C"),
        "d50m57c0": (0x0038, 0.016787, -50.138, "°C"),
        "d60m57a0": (0x00AD, 0.016787, -50.138, "°C"),
        "d50m47a":  (0x0038, 0.016787, -50.138, "°C"),
        "d50m47b1": (0x009C, 0.016787, -50.138, "°C"),
        "d60m47a0": (0x00AD, 0.016787, -50.138, "°C"),
    },
    "FTScd_tFuel": {
        "description": "Fuel temperature",
        "d50m57a0": (0x003C, 0.016787, -50.138, "°C"),
        "d50m57b1": (0x005B, 0.016787, -50.138, "°C"),
        "d60m57a0": (0x00B1, 0.016787, -50.138, "°C"),
        "d50m47a":  (0x003C, 0.016787, -50.138, "°C"),
        "d50m47b1": (0x005B, 0.016787, -50.138, "°C"),
        "d60m47a0": (0x00B1, 0.016787, -50.138, "°C"),
    },

    # ==================== ELECTRICAL ====================
    "BattCD_u": {
        "description": "Battery voltage",
        "d50m57a0": (0x002F, 0.002456, 0.0, "V"),
        "d50m57b1": (0x0093, 0.002456, 0.0, "V"),
        "d50m57c0": (0x002F, 0.002456, 0.0, "V"),
        "d60m57a0": (0x0093, 0.002456, 0.0, "V"),
        "d62m57a0": (0x0093, 0.002456, 0.0, "V"),
        "d50m47a":  (0x002F, 0.002456, 0.0, "V"),
        "d50m47b1": (0x0093, 0.002456, 0.0, "V"),
        "d60m47a0": (0x0093, 0.002456, 0.0, "V"),
    },

    # ==================== BOOST / ATMOSPHERE ====================
    "APSCD_pVal": {
        "description": "Boost pressure (absolute)",
        "d50m57a0": (0x006E, 0.125002, 0.0, "hPa"),
        "d50m57b1": (0x006E, 0.125002, 0.0, "hPa"),
        "d50m57c0": (0x006E, 0.125002, 0.0, "hPa"),
        "d60m57a0": (0x008B, 0.125002, 0.0, "hPa"),
        "d62m57a0": (0x008B, 0.125002, 0.0, "hPa"),
        "d50m47a":  (0x006E, 0.125002, 0.0, "hPa"),
        "d50m47b1": (0x006E, 0.125002, 0.0, "hPa"),
        "d60m47a0": (0x008B, 0.125002, 0.0, "hPa"),
    },
    "BPSCD_pOutVal": {
        "description": "Atmospheric pressure",
        "d50m57a0": (0x003A, 0.125002, 0.0, "hPa"),
        "d50m57b1": (0x009E, 0.125002, 0.0, "hPa"),
        "d50m57c0": (0x003A, 0.125002, 0.0, "hPa"),
        "d60m57a0": (0x0091, 0.125002, 0.0, "hPa"),
        "d50m47a":  (0x003A, 0.125002, 0.0, "hPa"),
        "d50m47b1": (0x009E, 0.125002, 0.0, "hPa"),
        "d60m47a0": (0x0091, 0.125002, 0.0, "hPa"),
    },

    # ==================== RAIL PRESSURE ====================
    "RailCD_pPeak": {
        "description": "Rail pressure actual",
        "d50m57a0": (0x00C2, 0.030518, 0.0, "bar"),
        "d50m57b1": (0x00C2, 0.030518, 0.0, "bar"),
        "d50m57c0": (0x00C2, 0.030518, 0.0, "bar"),
        "d60m57a0": (0x00DF, 0.030518, 0.0, "bar"),
        "d62m57a0": (0x00DF, 0.030518, 0.0, "bar"),
        "d50m47a":  (0x00C2, 0.030518, 0.0, "bar"),
        "d50m47b1": (0x00C2, 0.030518, 0.0, "bar"),
        "d60m47a0": (0x00DF, 0.030518, 0.0, "bar"),
    },
    "Rail_pSetPoint": {
        "description": "Rail pressure target",
        "d50m57a0": (0x00C3, 0.030518, 0.0, "bar"),
        "d50m57b1": (0x00C3, 0.030518, 0.0, "bar"),
        "d50m57c0": (0x00C3, 0.030518, 0.0, "bar"),
        "d60m57a0": (0x00E1, 0.030518, 0.0, "bar"),
        "d62m57a0": (0x00E1, 0.030518, 0.0, "bar"),
        "d50m47a":  (0x00C3, 0.030518, 0.0, "bar"),
        "d50m47b1": (0x00C3, 0.030518, 0.0, "bar"),
        "d60m47a0": (0x00E1, 0.030518, 0.0, "bar"),
    },

    # ==================== AIR MASS ====================
    "AFSCD_dmAirPerTime": {
        "description": "Air mass flow",
        "d50m57a0": (0x002E, 0.048829, -1599.971, "Kg/h"),
        "d50m57b1": (0x0052, 0.048829, -1599.971, "Kg/h"),
        "d50m57c0": (0x002E, 0.048829, -1599.971, "Kg/h"),
        "d60m57a0": (0x0080, 0.048829, -1599.971, "Kg/h"),
        "d50m47a":  (0x002E, 0.048829, -1599.971, "Kg/h"),
        "d50m47b1": (0x0052, 0.048829, -1599.971, "Kg/h"),
        "d60m47a0": (0x0080, 0.048829, -1599.971, "Kg/h"),
    },

    # ==================== FUEL INJECTION ====================
    "InjCtl_qCurr": {
        "description": "Fuel quantity actual (per cycle)",
        "d50m57a0": (0x0055, 0.003052, -99.999, "mg/cyc"),
        "d50m57b1": (0x0055, 0.003052, -99.999, "mg/cyc"),
        "d50m57c0": (0x0055, 0.003052, -99.999, "mg/cyc"),
        "d60m57a0": (0x00B5, 0.003052, -99.999, "mg/cyc"),
        "d50m47a":  (0x0055, 0.003052, -99.999, "mg/cyc"),
        "d50m47b1": (0x0055, 0.003052, -99.999, "mg/cyc"),
        "d60m47a0": (0x00B5, 0.003052, -99.999, "mg/cyc"),
    },

    # ==================== PEDAL ====================
    "APPCD_rFlt": {
        "description": "Accelerator pedal position",
        "d50m57a0": (0x0066, 0.003052, 0.0, "%"),
        "d50m57b1": (0x0066, 0.003052, 0.0, "%"),
        "d50m57c0": (0x0066, 0.003052, 0.0, "%"),
        "d60m57a0": (0x0086, 0.003052, 0.0, "%"),
        "d50m47a":  (0x0066, 0.003052, 0.0, "%"),
        "d50m47b1": (0x0066, 0.003052, 0.0, "%"),
        "d60m47a0": (0x0086, 0.003052, 0.0, "%"),
    },

    # ==================== TORQUE ====================
    "CoEng_trq": {
        "description": "Engine torque",
        "d50m57b1": (0x14B6, 0.114445, -2500.060, "Nm"),
        "d60m57a0": (0x0097, 0.114445, -2500.060, "Nm"),
        "d62m57a0": (0x0097, 0.114445, -2500.060, "Nm"),
        "d50m47b1": (0x14B6, 0.114445, -2500.060, "Nm"),
        "d60m47a0": (0x0097, 0.114445, -2500.060, "Nm"),
    },

    # ==================== VEHICLE ====================
    "PFlt_vVehFlt_mp": {
        "description": "Vehicle speed",
        "d50m57a0": (0x0072, 0.003815, 0.0, "km/h"),
        "d50m57b1": (0x13FA, 0.003815, 0.0, "km/h"),
        "d60m57a0": (0x1918, 0.003815, 0.0, "km/h"),
        "d50m47a":  (0x0072, 0.003815, 0.0, "km/h"),
        "d50m47b1": (0x13FA, 0.003815, 0.0, "km/h"),
        "d60m47a0": (0x1918, 0.003815, 0.0, "km/h"),
    },
}


def get_params_for_ecu(ecu_name: str) -> list:
    """Get all parameters for a specific ECU.
    
    Args:
        ecu_name: PRG filename without extension, e.g. 'd50m57b1'
    
    Returns:
        List of dicts with keys: name, description, adr, fact_a, fact_b, unit
    """
    result = []
    for bosch_name, data in PARAM_DB.items():
        desc = data.get('description', bosch_name)
        if ecu_name in data:
            adr, fa, fb, unit = data[ecu_name]
            result.append({
                'name': bosch_name,
                'description': desc,
                'adr': adr,
                'fact_a': fa,
                'fact_b': fb,
                'unit': unit,
            })
    return result


def list_ecus() -> list:
    """List all ECU identifiers in the database."""
    ecus = set()
    for data in PARAM_DB.values():
        for key in data:
            if key != 'description':
                ecus.add(key)
    return sorted(ecus)


if __name__ == '__main__':
    print("Supported ECUs:", ', '.join(list_ecus()))
    print()
    for ecu in list_ecus():
        params = get_params_for_ecu(ecu)
        print(f"  {ecu}: {len(params)} key params")
