#!/usr/bin/env python3
"""
Convert a multi-sheet Excel file into individual CSV files.
Each sheet is saved as: <excel_name>_<sheet_name>.csv

Usage:
    python excel_to_csv.py <file.xlsx> [output_dir]

Examples:
    python excel_to_csv.py data.xlsx
    python excel_to_csv.py data.xlsx ./output
"""

import sys
import os
import pandas as pd


def excel_to_csv(excel_path: str, output_dir: str = None):
    if not os.path.exists(excel_path):
        print(f"Error: File not found: {excel_path}")
        sys.exit(1)

    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(excel_path))

    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(excel_path))[0]
    sheets = pd.read_excel(excel_path, sheet_name=None)

    print(f"Found {len(sheets)} sheet(s) in '{excel_path}'")

    for sheet_name, df in sheets.items():
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in sheet_name).strip()
        csv_filename = f"{base_name}_{safe_name}.csv"
        csv_path = os.path.join(output_dir, csv_filename)

        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  ✓ '{sheet_name}' → {csv_path}  ({len(df)} rows, {len(df.columns)} cols)")

    print(f"\nDone. {len(sheets)} CSV file(s) saved to: {output_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    excel_file = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else None

    excel_to_csv(excel_file, out_dir)