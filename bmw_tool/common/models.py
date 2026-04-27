"""
Common types for BMW diagnostic tool.

Defines ECU, Parameter, VehicleProfile dataclasses and protocol constants.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from enum import IntEnum


# ──────────────────────────────────────────────────────────
# Protocol types (on K-Line @ 9600 8N1 DTR=false)
# ──────────────────────────────────────────────────────────

class Protocol(IntEnum):
    """Frame format on K-Line."""
    DS2_CLASSIC = 1   # [ADDR][LEN][DATA...][XOR_CS]        — IKE, LCM, EWS3, ABS, ...
    KWP_EXT_B8  = 2   # [B8][DST][F1][LEN][DATA...][ADD_CS] — DDE, EGS
    KWP_STD_82  = 3   # [82][DST][F1][DATA...][ADD_CS]      — short header (rarely used)


# ──────────────────────────────────────────────────────────
# Known ECU addresses (common across E39/E46/E53)
# ──────────────────────────────────────────────────────────

# DS2 modules (7-bit source address)
ECU_DDE         = 0x12   # Diesel ECU         (but spoken via KWP_EXT_B8, not DS2)
ECU_EGS         = 0x18   # Automatic gearbox  (KWP_EXT_B8)
ECU_ABS         = 0x56   # ABS/DSC
ECU_EWS         = 0x44   # Immobilizer / ZCS coding source
ECU_IKE         = 0x80   # Instrument cluster
ECU_LCM         = 0xD0   # Light control module (LCM III/IV)
ECU_ZGM         = 0x00   # Zentral-Gateway-Modul
ECU_BC          = 0x57   # Bordcomputer (E39)
ECU_GM          = 0x00   # General Module
ECU_SRS         = 0x50   # Airbag
ECU_MRS         = 0x50   # Multiple Restraint System
ECU_PDC         = 0x60   # Park distance control
ECU_AIRBAG      = 0x50
ECU_EDC         = 0x00   # Electronic damper control


# ──────────────────────────────────────────────────────────
# Parameter (single measurement value readable from DDE)
# ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Parameter:
    """A single scalar measurement in DDE memory."""
    name: str              # Bosch internal name, e.g. "Eng_nAvrg"
    addr: int              # 16-bit memory address in DDE
    size: int              # bytes (1, 2, or 4)
    factor_a: float        # linear scale: phys = raw * a + b
    factor_b: float
    unit: str              # display unit
    description: str = ""  # German description
    signed: bool = False   # if raw value is signed


# ──────────────────────────────────────────────────────────
# ECU on a vehicle
# ──────────────────────────────────────────────────────────

@dataclass
class EcuConfig:
    """One ECU accessible on the vehicle."""
    addr: int               # 7-bit address (0x12, 0x44, ...)
    protocol: Protocol      # frame format
    name: str               # short name ("DDE", "IKE", ...)
    description: str = ""   # human readable ("Digital Diesel Electronics")
    needs_wakeup: bool = False  # True for DDE5 — requires A2 F8 wake first
    optional: bool = False  # True = may not be present on all variants


# ──────────────────────────────────────────────────────────
# Vehicle profile
# ──────────────────────────────────────────────────────────

@dataclass
class VehicleProfile:
    """Profile for a specific vehicle/engine variant."""
    id: str                    # unique slug ("e53_3.0d_m57tu_lci")
    name: str                  # human name ("E53 X5 3.0d M57TU LCI")
    series: str                # "E39", "E46", "E53"
    engine: str                # "M47", "M57", "M57TU"
    dde_sgbd: str              # PRG file base ("d50m57b1")
    
    # VIN matching: list of (prefix, type_key_pattern) tuples
    # Prefix is first 7 chars of VIN (WBAFB71 etc)
    vin_prefixes: List[str] = field(default_factory=list)
    
    # ECUs present on this vehicle
    ecus: List[EcuConfig] = field(default_factory=list)
    
    # Key DDE parameters (subset we actually display)
    # Loaded from extracted CSV files at startup
    dde_params: List[Parameter] = field(default_factory=list)
    
    def find_ecu(self, addr: int) -> Optional[EcuConfig]:
        for e in self.ecus:
            if e.addr == addr:
                return e
        return None
    
    def find_param(self, name: str) -> Optional[Parameter]:
        for p in self.dde_params:
            if p.name == name:
                return p
        return None


# ──────────────────────────────────────────────────────────
# Standard ECU set for E39/E46/E53 diesels
# ──────────────────────────────────────────────────────────

def standard_diesel_ecus() -> List[EcuConfig]:
    """
    Typical ECU inventory for E39/E46/E53 diesel vehicles on K-Line.
    Individual profiles can add/remove entries as needed.
    """
    return [
        EcuConfig(ECU_DDE, Protocol.KWP_EXT_B8, "DDE",
                  "Digital Diesel Electronics", needs_wakeup=True),
        EcuConfig(ECU_EGS, Protocol.KWP_EXT_B8, "EGS",
                  "Automatic gearbox", optional=True),
        EcuConfig(ECU_EWS, Protocol.DS2_CLASSIC, "EWS",
                  "Immobilizer EWS3"),
        EcuConfig(ECU_IKE, Protocol.DS2_CLASSIC, "IKE",
                  "Instrument cluster"),
        EcuConfig(ECU_LCM, Protocol.DS2_CLASSIC, "LCM",
                  "Light control module", optional=True),
        EcuConfig(ECU_ABS, Protocol.DS2_CLASSIC, "ABS",
                  "ABS/DSC", optional=True),
    ]
