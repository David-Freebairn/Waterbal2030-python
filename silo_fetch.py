"""
SILO climate data fetcher for PERFECT model
Fetches daily data from the SILO DataDrill API (gridded interpolated surface)
and returns a DataFrame in the same format as read_met() in perfect_io.py

API endpoint: DataDrillDataset.php
  - No station number needed — works for any lat/lon in Australia
  - Password is always "apirequest"
  - Username must be a valid email address
  - Returns CSV with daily: rain, tmax, tmin, evap, radiation, VP, RH etc.

Usage:
    from silo_fetch import fetch_silo
    lat, df = fetch_silo(
        lat=-27.28, lon=151.26,
        start='18890101', end='20241231',
        email='your@email.com'
    )
"""

import requests
import pandas as pd
import numpy as np
import io
from pathlib import Path


SILO_URL = "https://www.longpaddock.qld.gov.au/cgi-bin/silo/DataDrillDataset.php"

# Variables we need for PERFECT:
#   daily_rain, max_temp, min_temp, evap_pan, rh_tmax, rh_tmin, radiation
# SILO comment codes for CSV format - request all key variables
VARIABLES = "daily_rain,max_temp,min_temp,evap_pan,rh_tmax,rh_tmin,radiation"


def fetch_silo(lat, lon, start, end, email, cache_path=None):
    """
    Fetch daily SILO DataDrill data for a lat/lon point.

    Parameters
    ----------
    lat : float        Latitude (negative = south)
    lon : float        Longitude
    start : str        Start date YYYYMMDD
    end : str          End date YYYYMMDD
    email : str        Your email (used as API username — required by SILO)
    cache_path : str   Optional path to cache CSV locally (avoids re-downloading)

    Returns
    -------
    lat : float
    df : pd.DataFrame  Daily climate indexed by date, same columns as read_met()
    """

    # -- check cache ----------------------------------------------------------
    if cache_path and Path(cache_path).exists():
        print(f"  Loading cached SILO data from {cache_path}")
        df = pd.read_csv(cache_path, index_col='date', parse_dates=True)
        return lat, df

    # -- request --------------------------------------------------------------
    params = {
        'lat'      : lat,
        'lon'      : lon,
        'start'    : start,
        'finish'   : end,
        'format'   : 'csv',
        'comment'  : VARIABLES,
        'username' : email,
        'password' : 'apirequest',
    }

    print(f"  Fetching SILO data for ({lat}, {lon})  {start}–{end} ...")
    # SILO web application firewall requires a browser-like User-Agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/plain, text/csv, */*',
        'Referer': 'https://www.longpaddock.qld.gov.au/silo/',
    }
    resp = requests.get(SILO_URL, params=params, headers=headers, timeout=120)
    resp.raise_for_status()

    raw = resp.text

    # -- parse CSV  -----------------------------------------------------------
    # SILO CSV has a multi-line header; data lines start with a date (digit)
    lines = raw.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        # The column header line starts with 'Date'
        if stripped.lower().startswith('date'):
            header_idx = i
            break

    if header_idx is None:
        if "rejected" in raw.lower() or "support id" in raw.lower():
            raise ValueError(
                "SILO request rejected by server firewall.\n"
                "  The request was blocked before reaching the data server.\n"
                "  Solutions to try:\n"
                "    1. Check your internet connection\n"
                "    2. Try again in a few minutes (SILO sometimes rate-limits)\n"
                "    3. Try from a different network (e.g. mobile hotspot)\n"
                "    4. Download data manually from https://www.longpaddock.qld.gov.au/silo/\n"
                "       then use a .P51 file in the launcher instead."
            )
        raise ValueError(f"Could not parse SILO response. First 20 lines:\n" +
                         "\n".join(lines[:20]))

    csv_text = "\n".join(lines[header_idx:])
    raw_df = pd.read_csv(io.StringIO(csv_text))

    # Normalise column names to lowercase, strip whitespace
    raw_df.columns = [c.strip().lower() for c in raw_df.columns]

    # -- build standardised DataFrame matching perfect_io.read_met() output --
    df = pd.DataFrame()
    df.index = pd.to_datetime(raw_df['date'].astype(str), format='%Y%m%d')
    df.index.name = 'date'

    df['year']  = df.index.year
    df['month'] = df.index.month
    df['day']   = df.index.day
    df['doy']   = df.index.day_of_year

    # Map SILO column names → PERFECT names
    col_map = {
        'daily_rain' : 'rain',
        'max_temp'   : 'tmax',
        'min_temp'   : 'tmin',
        'evap_pan'   : 'epan',
        'rh_tmax'    : 'rhmax',   # RH at time of Tmax (approx = RHmin)
        'rh_tmin'    : 'rhmin',   # RH at time of Tmin (approx = RHmax)
        'radiation'  : 'radiation',  # MJ/m2/day — bonus variable not in old .MET
    }
    for silo_col, our_col in col_map.items():
        if silo_col in raw_df.columns:
            df[our_col] = raw_df[silo_col].values
        else:
            df[our_col] = np.nan

    df['tmean'] = (df['tmax'] + df['tmin']) / 2.0

    # -- cache ----------------------------------------------------------------
    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_path)
        print(f"  Cached to {cache_path}")

    print(f"  Done — {len(df)} days  ({df.index[0].date()} to {df.index[-1].date()})")
    return lat, df


def silo_to_met_file(df, lat, out_path):
    """
    Write a DataFrame (from fetch_silo) back to PERFECT .MET format.
    Useful for feeding existing PERFECT exe or for archiving.
    """
    out_path = Path(out_path)
    with open(out_path, 'w') as f:
        f.write(f"{lat:.2f}\n")
        for row in df.itertuples():
            date_int = row.Index.year * 10000 + row.Index.month * 100 + row.Index.day
            epan = row.epan if not np.isnan(row.epan) else 0.0
            rhmax = row.rhmax if not np.isnan(row.rhmax) else 0.0
            rhmin = row.rhmin if not np.isnan(row.rhmin) else 0.0
            f.write(f" {date_int:8d} {row.doy:3d}  "
                    f"{row.tmax:5.1f}  {row.tmin:5.1f}  "
                    f"{row.rain:6.1f}  {epan:5.1f}  "
                    f"{rhmax:5.1f}  {rhmin:5.1f}\n")
    print(f"  Written .MET file: {out_path}")


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys

    email = sys.argv[1] if len(sys.argv) > 1 else input("Enter your email for SILO API: ")

    # Dalby, QLD
    LAT, LON = -27.28, 151.26

    lat, df = fetch_silo(
        lat=LAT, lon=LON,
        start='18890101',
        end='20241231',
        email=email,
        cache_path='/home/claude/perfect/cache/dalby_silo.csv'
    )

    print(f"\nLatitude : {lat}")
    print(f"Period   : {df.index[0].date()} to {df.index[-1].date()}")
    print(f"Days     : {len(df)}")
    print(f"\nSample:")
    print(df[['tmax','tmin','rain','epan','rhmin','rhmax','radiation']].head())

    # Optionally write a .MET file
    silo_to_met_file(df, lat, '/mnt/user-data/outputs/DALBY_SILO.MET')
