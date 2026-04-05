#!/usr/bin/env python3
"""
BMW PRG Parameter Extractor
=============================
Extracts BetriebswTab (measurement parameters) from compiled BEST1 .PRG files.

Usage:
  python3 prg_extractor.py d50m57b1.prg
  python3 prg_extractor.py d50m57b1.prg --csv output.csv
  python3 prg_extractor.py d50m57b1.prg d60m47a0.prg --compare
  python3 prg_extractor.py *.prg --csv all_params.csv
"""
import sys, os, csv, argparse

XOR_KEY = 0xF7

def decode_prg(data: bytes) -> bytearray:
    return bytearray(b ^ XOR_KEY for b in data)

def get_ecu_desc(decoded: bytearray) -> str:
    for search in [b'DDE ', b'DME ', b'SGBD']:
        pos = decoded.find(search, 0x80, 0x400)
        if pos >= 0:
            end = decoded.find(0, pos)
            if end > pos:
                return bytes(decoded[pos:min(end, pos+80)]).decode('ascii', errors='replace')
    return "Unknown"

def extract_params(filepath: str) -> tuple:
    with open(filepath, 'rb') as f:
        data = f.read()
    decoded = decode_prg(data)
    ecu = get_ecu_desc(decoded)
    
    pattern = b'B812F1'
    entries = []
    seen = set()
    i = 0
    while i < len(decoded) - 100:
        pos = decoded.find(pattern, i)
        if pos < 0: break
        
        ne = pos - 1
        if ne < 0 or decoded[ne] != 0: i = pos + 1; continue
        ns = ne
        while ns > 0 and decoded[ns-1] != 0: ns -= 1
        name = bytes(decoded[ns:ne]).decode('ascii', errors='replace')
        
        fields = []
        fp = pos
        for _ in range(15):
            fe = decoded.find(0, fp)
            if fe < 0 or fe - fp > 60: break
            fields.append(bytes(decoded[fp:fe]).decode('ascii', errors='replace'))
            fp = fe + 1
        
        if len(fields) >= 10 and len(name) >= 3 and '_' in name and name not in seen:
            seen.add(name)
            entries.append({
                'name': name,
                'telegram': fields[0] if fields else '',
                'adr': fields[3] if len(fields) > 3 else '',
                'size': fields[4] if len(fields) > 4 else '',
                'fact_a': fields[8] if len(fields) > 8 else '',
                'fact_b': fields[9] if len(fields) > 9 else '',
                'unit': fields[13] if len(fields) > 13 else '',
            })
        i = pos + 1
    return ecu, entries

def main():
    ap = argparse.ArgumentParser(description='BMW PRG Parameter Extractor')
    ap.add_argument('files', nargs='+', help='PRG files to process')
    ap.add_argument('--csv', type=str, help='Output CSV file')
    ap.add_argument('--compare', action='store_true', help='Compare params across files')
    ap.add_argument('--filter', type=str, help='Filter by keyword (e.g. "Rail,Boost,Eng")')
    args = ap.parse_args()
    
    all_results = {}
    for filepath in args.files:
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}", file=sys.stderr)
            continue
        base = os.path.splitext(os.path.basename(filepath))[0]
        ecu, entries = extract_params(filepath)
        all_results[base] = (ecu, entries)
        print(f"✓ {base:20s} [{ecu:40s}] → {len(entries)} params")
    
    if not all_results:
        print("No files processed"); return
    
    # Filter
    if args.filter:
        keywords = [k.strip().lower() for k in args.filter.split(',')]
        for base in all_results:
            ecu, entries = all_results[base]
            entries = [e for e in entries if any(kw in e['name'].lower() for kw in keywords)]
            all_results[base] = (ecu, entries)
    
    # CSV output
    if args.csv:
        with open(args.csv, 'w', newline='') as f:
            w = csv.writer(f)
            if args.compare:
                # Comparison mode: params as rows, files as columns
                all_names = set()
                for _, entries in all_results.values():
                    all_names.update(e['name'] for e in entries)
                
                header = ['Parameter', 'Unit']
                for base in all_results:
                    header += [f'{base} ADR', f'{base} FACT_A', f'{base} FACT_B']
                w.writerow(header)
                
                for name in sorted(all_names):
                    row = [name, '']
                    for base, (ecu, entries) in all_results.items():
                        entry = next((e for e in entries if e['name'] == name), None)
                        if entry:
                            if not row[1]: row[1] = entry['unit']
                            row += [entry['adr'], entry['fact_a'], entry['fact_b']]
                        else:
                            row += ['', '', '']
                    w.writerow(row)
            else:
                # Flat mode
                w.writerow(['File', 'ECU', 'Parameter', 'ADR', 'FACT_A', 'FACT_B', 'Unit'])
                for base, (ecu, entries) in all_results.items():
                    for e in entries:
                        w.writerow([base, ecu, e['name'], e['adr'], e['fact_a'], e['fact_b'], e['unit']])
        print(f"\nCSV saved: {args.csv}")
    
    # Print summary
    if not args.csv or args.compare:
        print()
        for base, (ecu, entries) in all_results.items():
            if len(all_results) > 1:
                print(f"\n=== {base} ({ecu}) ===")
            print(f"{'Parameter':35s} {'ADR':10s} {'FACT_A':14s} {'FACT_B':14s} {'Unit'}")
            print("-" * 85)
            for e in entries[:50]:  # limit output
                print(f"{e['name']:35s} {e['adr']:10s} {e['fact_a']:14s} {e['fact_b']:14s} {e['unit']}")
            if len(entries) > 50:
                print(f"  ... and {len(entries)-50} more")

if __name__ == '__main__':
    main()
