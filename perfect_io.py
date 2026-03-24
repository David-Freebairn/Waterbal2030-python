"""
PERFECT Model - Python Port
I/O utilities: climate and crop parameter readers
"""

import pandas as pd
import numpy as np
from pathlib import Path


# ---------------------------------------------------------------------------
# Climate / met file
# ---------------------------------------------------------------------------

def read_met(filepath):
    """
    Read a PERFECT .MET file.

    Format:
      Line 1: latitude (degrees, negative = south)
      Lines 2+: YYYYMMDD  DOY  Tmax  Tmin  Rain  Epan  RHmax  RHmin

    Returns
    -------
    lat : float
        Station latitude (degrees)
    df : pd.DataFrame
        Daily climate with columns:
        date, year, month, day, doy, tmax, tmin, rain, epan, rhmax, rhmin
    """
    filepath = Path(filepath)
    with open(filepath, 'r') as f:
        lines = f.readlines()

    lat = float(lines[0].strip())

    records = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 7:
            continue
        date_int = int(parts[0])
        year  = date_int // 10000
        month = (date_int % 10000) // 100
        day   = date_int % 100
        records.append({
            'date'  : pd.Timestamp(year=year, month=month, day=day),
            'year'  : year,
            'month' : month,
            'day'   : day,
            'doy'   : int(parts[1]),
            'tmax'  : float(parts[2]),
            'tmin'  : float(parts[3]),
            'rain'  : float(parts[4]),
            'epan'  : float(parts[5]),
            'rhmax' : float(parts[6]),
            'rhmin' : float(parts[7]) if len(parts) > 7 else np.nan,
        })

    df = pd.DataFrame(records).set_index('date')
    df['tmean'] = (df['tmax'] + df['tmin']) / 2.0
    return lat, df


# ---------------------------------------------------------------------------
# Crop parameter files
# ---------------------------------------------------------------------------

def read_crp_standard(filepath):
    """
    Read a standard PERFECT .CRP file (internal flag = 5).
    Returns a dict of crop parameters.
    """
    filepath = Path(filepath)
    lines = [l.rstrip() for l in open(filepath)]

    def val(line):
        """Extract leading numeric token(s) from a line."""
        return line.split()[:2]

    name = lines[0].strip()
    flag = int(lines[1].split()[0])

    p = {'name': name, 'flag': flag, 'file': filepath.name}

    v = lines[2].split();  p['plant_day_default'] = int(v[0]);  p['plant_month_default'] = int(v[1])
    v = lines[3].split();  p['plant_rain_mm'] = float(v[0]);    p['plant_rain_days'] = int(v[1])
    v = lines[4].split();  p['sw_depth_mm'] = float(v[0]);      p['sw_fraction'] = float(v[1])
    v = lines[5].split();  p['sw_surf_min'] = float(v[0]);      p['sw_surf_max'] = float(v[1])
    v = lines[6].split();  p['plant_window_start'] = int(v[0]); p['plant_window_end'] = int(v[1])
    p['min_fallow_days'] = int(lines[7].split()[0])
    p['lai_max']         = float(lines[8].split()[0])
    p['degree_days_total'] = float(lines[9].split()[0])
    p['prop_season_max_lai'] = float(lines[10].split()[0])
    p['lai_pt1_prop']    = float(lines[11].split()[0])
    p['lai_pt1_season']  = float(lines[12].split()[0])
    p['lai_pt2_prop']    = float(lines[13].split()[0])
    p['lai_pt2_season']  = float(lines[14].split()[0])
    p['senescence_coef'] = float(lines[15].split()[0])
    p['rue']             = float(lines[16].split()[0])   # g/MJ
    p['harvest_index']   = float(lines[17].split()[0])
    p['base_temp']       = float(lines[18].split()[0])
    p['opt_temp']        = float(lines[19].split()[0])
    p['max_root_depth']  = float(lines[20].split()[0])
    p['root_growth_day'] = float(lines[21].split()[0])
    p['water_stress_threshold'] = float(lines[22].split()[0])
    p['stress_kill_days']= int(lines[23].split()[0])
    p['max_residue_cover']= float(lines[24].split()[0])
    p['ratoon']          = lines[25].split()[0].upper() == 'Y'
    p['n_ratoons']       = int(lines[26].split()[0])
    p['ratoon_scale']    = float(lines[27].split()[0])

    return p


def read_all_crp(folder):
    """
    Read all .CRP files in a folder. Returns dict keyed by 2-letter code.
    Skips non-standard crop types (wheat flag=1, sunflower flag=2, ET flag=4).
    """
    folder = Path(folder)
    crops = {}
    for f in sorted(folder.glob('*.[Cc][Rr][Pp]')):
        try:
            with open(f) as fh:
                lines = fh.readlines()
            flag = int(lines[1].split()[0])
            if flag == 5:
                p = read_crp_standard(f)
                code = f.stem.upper()
                crops[code] = p
        except Exception as e:
            print(f"  Skipped {f.name}: {e}")
    return crops


# ---------------------------------------------------------------------------
# Quick summary helpers
# ---------------------------------------------------------------------------

def met_summary(df):
    """Annual summary statistics from daily met dataframe."""
    ann = df.groupby('year').agg(
        rain_mm   = ('rain',  'sum'),
        tmax_mean = ('tmax',  'mean'),
        tmin_mean = ('tmin',  'mean'),
        epan_sum  = ('epan',  'sum'),
        rain_days = ('rain',  lambda x: (x > 0).sum()),
    ).round(1)
    return ann


if __name__ == '__main__':
    import sys
    met_path = sys.argv[1] if len(sys.argv) > 1 else '../uploads/DALBY.MET'
    lat, df = read_met(met_path)
    print(f"Latitude: {lat}")
    print(f"Period: {df.index[0].date()} to {df.index[-1].date()}  ({len(df)} days)")
    print(f"\nAnnual summary (first 5 years):")
    print(met_summary(df).head())
