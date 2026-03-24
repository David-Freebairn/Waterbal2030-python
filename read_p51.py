"""
SILO P51 file reader
====================
Parses the standard SILO .P51 point data format and returns a DataFrame
in the same structure as read_met() and fetch_silo() so it drops straight
into run_simulation without any other changes.

P51 format:
  Line 1  : lat lon station_number station_name
  Lines 2+ : // comment lines (any number)
  Header  : date jday tmax tmin rain evap rad vp
  Data    : YYYYMMDD,jday,tmax,tmin,rain,evap,rad,vp[,]
              (trailing comma present on some rows — handled automatically)

Columns returned (matching fetch_silo / read_met):
  date, year, month, day, doy, tmax, tmin, tmean,
  rain, epan, radiation, vp
"""

import pandas as pd
import numpy as np
from pathlib import Path


def read_p51(filepath):
    """
    Parse a SILO .P51 climate file.

    Parameters
    ----------
    filepath : str or Path

    Returns
    -------
    lat : float        Station latitude (negative = south)
    df  : pd.DataFrame Daily climate indexed by date
    """
    filepath = Path(filepath)

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()

    # Normalise line endings (handles Windows \r\n, old Mac \r, Unix \n)
    lines = raw.replace('\r\n', '\n').replace('\r', '\n').split('\n')

    # ── line 1: lat lon station_no name ──────────────────────────────────
    parts = lines[0].strip().split(None, 3)
    lat  = float(parts[0])
    lon  = float(parts[1])
    stn  = parts[2] if len(parts) > 2 else ''
    name = parts[3] if len(parts) > 3 else filepath.stem

    # ── skip comment/blank lines and find header ──────────────────────────
    header_idx = None
    for i, line in enumerate(lines[1:], 1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('//') or stripped.startswith('#'):
            continue
        if stripped.lower().startswith('date'):
            header_idx = i
            break

    if header_idx is None:
        raise ValueError(f"Could not find header line in {filepath.name}")

    # ── parse column names from header ────────────────────────────────────
    # Header is space-separated: "date jday tmax tmin rain evap rad vp"
    header_cols = lines[header_idx].strip().lower().split()

    # ── parse data lines ──────────────────────────────────────────────────
    # Data lines are comma-separated with an optional trailing comma
    records = []
    skipped = 0
    for line in lines[header_idx + 1:]:
        stripped = line.strip()
        if not stripped:
            continue
        # Support both comma-delimited and whitespace-delimited data rows
        if ',' in stripped:
            row = stripped.rstrip(',').split(',')
        else:
            row = stripped.split()
        if len(row) < 5:
            skipped += 1
            continue
        try:
            date_int = int(str(row[0]).strip())
        except ValueError:
            skipped += 1
            continue

        year  = date_int // 10000
        month = (date_int % 10000) // 100
        day   = date_int % 100

        rec = {
            'date' : pd.Timestamp(year=year, month=month, day=day),
            'year' : year,
            'month': month,
            'day'  : day,
            'doy'  : int(row[1]) if len(row) > 1 else np.nan,
        }

        # Map remaining columns by position using header_cols
        col_map = {
            'tmax': 'tmax', 'tmin': 'tmin',
            'rain': 'rain', 'evap': 'epan',
            'rad' : 'radiation', 'vp': 'vp',
        }
        for j, col in enumerate(header_cols[2:], 2):
            key = col_map.get(col, col)
            if j < len(row):
                try:
                    rec[key] = float(row[j])
                except ValueError:
                    rec[key] = np.nan
            else:
                rec[key] = np.nan

        records.append(rec)

    if not records:
        first_data = repr(lines[header_idx+1]) if len(lines) > header_idx+1 else 'N/A'
        raise ValueError(
            f"{filepath.name}: parsed 0 data rows (skipped {skipped} lines).\n"
            f"  Header found at line {header_idx}: {lines[header_idx]!r}\n"
            f"  First data line after header: {first_data}"
        )

    df = pd.DataFrame(records).set_index('date')
    df['tmean'] = (df['tmax'] + df['tmin']) / 2.0

    # Ensure columns expected by the water balance model exist
    for col in ['rain', 'epan', 'tmax', 'tmin', 'radiation']:
        if col not in df.columns:
            df[col] = np.nan

    # Fill missing epan with NaN (some P51 files omit it)
    if df['epan'].isna().all():
        print(f"  Warning: no pan evaporation in {filepath.name} — epan set to 0")
        df['epan'] = 0.0

    print(f"  Loaded {filepath.name}: {name} ({lat:.3f}, {lon:.3f})")
    print(f"  Period: {df.index[0].date()} to {df.index[-1].date()}  "
          f"({len(df)} days, {df.index.year.nunique()} years)")

    return lat, df


if __name__ == '__main__':
    import sys
    fpath = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/uploads/Greenwood.p51'
    lat, df = read_p51(fpath)
    print(f"\nColumns : {list(df.columns)}")
    print(f"\nSummary:")
    print(df[['tmax','tmin','rain','epan','radiation']].describe().round(2))
    print(f"\nFirst 5 rows:")
    print(df.head())
