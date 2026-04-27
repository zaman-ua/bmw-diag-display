#!/usr/bin/env python3
"""
Universal DDE BetriebswTab parameter extractor.

Extracts measurement parameter table from any BMW DDE4/DDE5 PRG file.

Record format (null-separated fields after telegram):
    [BoschName] [Telegram_hex] [block?] [size] [adr_hex] [adr2_hex]
    [?] [?] [?] [factor_a] [factor_b] [?] [?] [format] [unit]
    [empty] [BoschName_repeat] [Description]
"""
import sys, os, re, csv
from dataclasses import dataclass
from typing import List


@dataclass
class Parameter:
    name: str
    addr: int
    size: int
    factor_a: float
    factor_b: float
    unit: str
    fmt: str
    description: str
    telegram: str


def decode_prg(filepath: str) -> bytes:
    with open(filepath, 'rb') as f:
        raw = f.read()
    return bytes(b ^ 0xF7 for b in raw[0xa0:])


def extract_parameters(filepath: str) -> List[Parameter]:
    """
    Strategy:
      1. Find every KWP2000 telegram string (B812F1...) in the data.
      2. For each match, read the name field that precedes the telegram
         (walk back from telegram_start to the previous null byte) AND
         parse the 20 null-separated fields after the telegram.
      3. Validate: size must be 1..8, address must be <= 0xFFFF,
         factor_a/factor_b must parse as floats.
      4. Use the "name_repeat" field (index 14 or 15) as the canonical name
         if it differs from the preceding name — this handles both DDE4
         (where the preceding identifier may be the German result name)
         and DDE5 layouts.
    """
    data = decode_prg(filepath)
    
    telegram_re = re.compile(rb'\x00(B812F1[0-9A-F]+)\x00')
    
    params = []
    seen = set()
    
    for tm in telegram_re.finditer(data):
        tel_start = tm.start() + 1
        tel_end = tm.end() - 1
        telegram = data[tel_start:tel_end].decode('latin1')
        
        # Walk back to find preceding name (ends at tel_start - 1)
        pre_end = tel_start - 1
        pre_start = pre_end
        while pre_start > 0 and data[pre_start - 1] != 0:
            pre_start -= 1
        if pre_end - pre_start < 2:
            continue
        try:
            pre_name = data[pre_start:pre_end].decode('latin1')
        except:
            continue
        
        # Parse 20 null-separated fields after telegram
        pos = tel_end + 1
        fields = []
        for _ in range(20):
            field_end = data.find(b'\x00', pos)
            if field_end == -1 or field_end - pos > 200:
                break
            try:
                field = data[pos:field_end].decode('latin1')
            except:
                break
            fields.append(field)
            pos = field_end + 1
        
        if len(fields) < 14:
            continue
        
        # Detect DDE4 vs DDE5 format:
        #  DDE5 has addr_repeat at fields[3] (e.g., "0x002D")
        #  DDE4 has block tag "06" at fields[3]
        # Use fields[1] = size (must be 1..8 int) for validation,
        # then check if fields[3] starts with "0x"
        try:
            size = int(fields[1])
            addr = int(fields[2], 16)
        except (ValueError, IndexError):
            continue
        
        if not (1 <= size <= 8):
            continue
        if not (0 <= addr <= 0xFFFF):
            continue
        
        is_dde5 = len(fields) > 3 and fields[3].startswith('0x')
        
        if is_dde5:
            # DDE5 layout
            #  7: factor_a, 8: factor_b, 11: fmt, 12: unit, 14: name, 15: desc
            try:
                factor_a = float(fields[7])
                factor_b = float(fields[8])
                fmt = fields[11]
                unit = fields[12]
                name_field = fields[14] if len(fields) > 14 else ''
                desc = fields[15] if len(fields) > 15 else ''
            except (ValueError, IndexError):
                continue
        else:
            # DDE4 layout
            #  6: factor_a, 7: factor_b, 10: fmt, 11: unit, 13: name, 14: desc
            try:
                factor_a = float(fields[6])
                factor_b = float(fields[7])
                fmt = fields[10]
                unit = fields[11]
                name_field = fields[13] if len(fields) > 13 else ''
                desc = fields[14] if len(fields) > 14 else ''
            except (ValueError, IndexError):
                continue
        
        # Use name from field (canonical Bosch identifier)
        # Fallback to pre_name if field name is invalid
        if name_field and re.match(r'^[A-Za-z][A-Za-z0-9_\[\]]{1,40}$', name_field):
            name = name_field
        elif re.match(r'^[A-Za-z][A-Za-z0-9_\[\]]{1,40}$', pre_name):
            name = pre_name
        else:
            continue
        
        if len(name) < 2:
            continue
        
        if name in seen:
            continue
        seen.add(name)
        
        params.append(Parameter(
            name=name,
            addr=addr,
            size=size,
            factor_a=factor_a,
            factor_b=factor_b,
            unit=unit,
            fmt=fmt,
            description=desc,
            telegram=telegram,
        ))
    
    return params


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    filepath = sys.argv[1]
    print(f"Extracting from {os.path.basename(filepath)}...")
    params = extract_parameters(filepath)
    print(f"Found {len(params)} parameters")
    
    if not params:
        sys.exit(1)
    
    print("\nSample (first 15):")
    for p in params[:15]:
        print(f"  0x{p.addr:04X} {p.name:30s} sz={p.size}  "
              f"a={p.factor_a:>11.6f} b={p.factor_b:>+9.3f}  [{p.unit:6s}] {p.description[:30]}")
    
    if len(sys.argv) >= 3:
        out = sys.argv[2]
        with open(out, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['addr', 'name', 'size', 'factor_a', 'factor_b',
                        'unit', 'format', 'description'])
            for p in sorted(params, key=lambda x: x.addr):
                w.writerow([
                    f"0x{p.addr:04X}", p.name, p.size,
                    f"{p.factor_a:.6f}", f"{p.factor_b:.6f}",
                    p.unit, p.fmt, p.description,
                ])
        print(f"\nSaved to {out}")


if __name__ == '__main__':
    main()
