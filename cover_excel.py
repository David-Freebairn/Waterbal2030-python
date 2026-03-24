"""
Excel cover data reader for PERFECT-Python water balance model

Reads the 'Cover data for Howleaky' Excel format:
  Sheet: Main
  Row 0:  Title
  Row 1:  Count
  Row 2:  Header: Day/Month | Day No | Green Cover % | Residue Cover % | Root Depth mm | ...
  Row 3+: Data rows — one per breakpoint

Columns used:
  'Day No'          → day of year (1–365)
  'Green Cover %'   → green canopy cover (0–100)
  'Residue Cover %' → surface residue cover (0–100)
  'Root Depth mm'   → rooting depth (mm)

Total cover for runoff = min(green + residue, 100) %
Green cover for ET partitioning = green %
"""

import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass


@dataclass
class CoverSchedule:
    """Cover and root depth schedule read from Excel."""
    name         : str
    source_file  : str
    doy          : np.ndarray   # day of year breakpoints
    green_cover  : np.ndarray   # fraction (0–1)
    residue_cover: np.ndarray   # fraction (0–1)
    total_cover  : np.ndarray   # fraction (0–1)  = min(green+residue, 1)
    root_depth   : np.ndarray   # mm
    n_points     : int
    tue          : float = 0.0  # transpiration use efficiency (g/m²/mm)
    hi           : float = 0.0  # harvest index (0–1)


def read_cover_excel(filepath, sheet_name='Main') -> CoverSchedule:
    """
    Parse a Howleaky-format Excel cover data file.

    Parameters
    ----------
    filepath   : path to .xlsx file
    sheet_name : sheet to read (default 'Main')

    Returns
    -------
    CoverSchedule
    """
    filepath = Path(filepath)
    df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None)

    # Row 2 is the header row
    header_row = 2
    df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row)

    # Normalise column names
    df.columns = [str(c).strip() for c in df.columns]

    # Filter to valid schedule rows:
    #   - Day No must be numeric and 1-365
    #   - Day/Month column must look like a date string (contains '-')
    #     This excludes TUE/HI rows whose Day/Month is a label string
    df['_doy_num'] = pd.to_numeric(df['Day No'], errors='coerce')
    day_month_col  = df.columns[0]   # first column is Day/Month
    is_date_row    = df[day_month_col].astype(str).str.contains('-', na=False)
    df = df[df['_doy_num'].notna() &
            (df['_doy_num'] >= 1) &
            (df['_doy_num'] <= 365) &
            is_date_row].copy()
    df['Day No'] = df['_doy_num'].astype(int)
    df = df.drop(columns=['_doy_num'])

    n_points = len(df)   # actual schedule rows

    doy           = df['Day No'].values
    green_pct     = pd.to_numeric(df['Green Cover %'],   errors='coerce').fillna(0).values
    residue_pct   = pd.to_numeric(df['Residue Cover %'], errors='coerce').fillna(0).values
    root_mm       = pd.to_numeric(df['Root Depth mm'],   errors='coerce').fillna(0).values

    # Convert to fractions, cap total at 1.0
    green   = np.clip(green_pct   / 100.0, 0.0, 1.0)
    residue = np.clip(residue_pct / 100.0, 0.0, 1.0)
    # Fractional cover model: residue only covers bare-soil fraction
    # total = green + (1 - green) * residue
    total   = np.clip(green + (1.0 - green) * residue, 0.0, 1.0)

    # ── Read TUE and HI from rows below the last date entry ─────────────
    # Layout: last date row, blank row, TUE row (+2), HI row (+3).
    # Strategy 1: search col 0 for label keywords — robust to any schedule length.
    # Strategy 2: positional fallback using header_row + n_points + offset.
    tue_val = 0.0
    hi_val  = 0.0

    col0 = df_raw.iloc[:, 0].astype(str).str.lower()
    tue_mask = col0.str.contains("transpir", na=False) | col0.str.contains("effic", na=False)
    hi_mask  = col0.str.contains("harvest",  na=False)

    def _extract_scalar(row_idx):
        """Try columns 1, 2, 3 in order for the first numeric value in a row."""
        for col_idx in [1, 2, 3]:
            try:
                v = float(df_raw.iloc[row_idx, col_idx])
                if v == v:   # not NaN
                    return v
            except (ValueError, TypeError, IndexError):
                continue
        return 0.0

    if tue_mask.any():
        tue_val = _extract_scalar(tue_mask.idxmax())

    if hi_mask.any():
        hi_val = _extract_scalar(hi_mask.idxmax())

    # Positional fallback if label search found nothing
    if tue_val == 0.0:
        for offset in [2, 3]:
            try:
                tue_val = _extract_scalar(header_row + n_points + offset)
                if tue_val != 0.0:
                    break
            except (IndexError, TypeError):
                pass

    if hi_val == 0.0:
        for offset in [3, 4]:
            try:
                hi_val = _extract_scalar(header_row + n_points + offset)
                if hi_val != 0.0:
                    break
            except (IndexError, TypeError):
                pass

    print(f"  Cover schedule: {filepath.stem}  n_points={n_points}  "          f"TUE={tue_val:.1f} g/m²/mm  HI={hi_val:.2f}")

    return CoverSchedule(
        name          = filepath.stem,
        source_file   = str(filepath),
        doy           = doy,
        green_cover   = green,
        residue_cover = residue,
        total_cover   = total,
        root_depth    = root_mm,
        n_points      = n_points,
        tue           = tue_val,
        hi            = hi_val,
    )


def get_cover_state(schedule: CoverSchedule, doy: int):
    """
    Interpolate green cover (fraction), total cover (fraction),
    and root depth (mm) for a given day of year.

    Returns (green_cover, total_cover, root_depth_mm)
    """
    green = float(np.interp(doy, schedule.doy, schedule.green_cover))
    total = float(np.interp(doy, schedule.doy, schedule.total_cover))
    roots = float(np.interp(doy, schedule.doy, schedule.root_depth))
    return green, total, roots


def cover_schedule_to_vege(schedule: CoverSchedule, out_path=None):
    """
    Export a CoverSchedule as a simple CSV for inspection or archive.
    """
    df = pd.DataFrame({
        'doy'          : schedule.doy,
        'green_cover_pct'  : (schedule.green_cover   * 100).round(1),
        'residue_cover_pct': (schedule.residue_cover * 100).round(1),
        'total_cover_pct'  : (schedule.total_cover   * 100).round(1),
        'root_depth_mm'    : schedule.root_depth,
    })
    if out_path:
        df.to_csv(out_path, index=False)
        print(f"Saved: {out_path}")
    return df


if __name__ == '__main__':
    sch = read_cover_excel('/mnt/user-data/uploads/Cover_data_for_Howleaky.xlsx')

    print(f"Name        : {sch.name}")
    print(f"Source      : {sch.source_file}")
    print(f"Breakpoints : {sch.n_points}")
    print()
    print(f"{'DOY':>5}  {'Green%':>7}  {'Residue%':>9}  {'Total%':>7}  {'Root mm':>8}")
    print("-" * 45)
    for i in range(len(sch.doy)):
        print(f"{sch.doy[i]:>5}  {sch.green_cover[i]*100:>7.1f}  "
              f"{sch.residue_cover[i]*100:>9.1f}  {sch.total_cover[i]*100:>7.1f}  "
              f"{sch.root_depth[i]:>8.0f}")

    print()
    print("Sample interpolated values (mid-month):")
    print(f"{'Month':<6} {'DOY':>4}  {'Green%':>7}  {'Total%':>7}  {'Root mm':>8}")
    for m, d in zip(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
                    [15,  46,  74, 105, 135, 152, 182, 213, 244, 274, 305, 335]):
        g, t, r = get_cover_state(sch, d)
        print(f"{m:<6} {d:>4}  {g*100:>7.1f}  {t*100:>7.1f}  {r:>8.0f}")
