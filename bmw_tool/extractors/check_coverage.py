#!/usr/bin/env python3
"""
Verify dashboard template coverage across all extracted DDE files.
For each semantic concept in DASHBOARD_TEMPLATES, check which DDE
variants can provide a value and which can't.
"""
import sys, os, glob

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.params_db import load_params_csv, DASHBOARD_TEMPLATES


def main():
    csv_dir = '/tmp/bmw_csv'
    csv_files = sorted(glob.glob(f'{csv_dir}/*.csv'))
    
    # Load all
    loaded = {}
    for f in csv_files:
        name = os.path.basename(f).replace('.csv', '')
        loaded[name] = load_params_csv(f)
    
    # Sort columns: DDE4 first, then DDE5 by name
    sgbd_order = sorted(loaded.keys(), key=lambda x: (not x.startswith('d40'), x))
    
    # Header
    print(f"{'Concept':<16}", end=' ')
    for sgbd in sgbd_order:
        print(f"{sgbd[:9]:>10}", end=' ')
    print()
    print("─" * (17 + 11 * len(sgbd_order)))
    
    for concept, (label, unit, fmt, dde5_cands, dde4_cands) in DASHBOARD_TEMPLATES.items():
        print(f"{concept:<16}", end=' ')
        for sgbd in sgbd_order:
            params = loaded[sgbd]
            found = None
            for cand in dde5_cands + dde4_cands:
                if cand in params:
                    found = cand
                    break
            if found:
                print(f"{found[:10]:>10}", end=' ')
            else:
                print(f"{'─':>10}", end=' ')
        print()
    
    # Summary
    print("\n=== Coverage summary ===")
    for sgbd in sgbd_order:
        params = loaded[sgbd]
        covered = 0
        total = len(DASHBOARD_TEMPLATES)
        for concept, (_, _, _, d5, d4) in DASHBOARD_TEMPLATES.items():
            if any(c in params for c in d5 + d4):
                covered += 1
        print(f"  {sgbd:<15} {covered:>3}/{total}   ({100*covered//total}%)")


if __name__ == '__main__':
    main()
