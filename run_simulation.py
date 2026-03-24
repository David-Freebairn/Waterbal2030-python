"""
PERFECT-Python master simulation runner
Accepts a JSON config dict (from the frontend wizard), fetches climate from SILO,
parses soil and vege inputs, runs the water balance, and returns monthly results
as a JSON-serialisable dict ready for the dashboard.

Usage:
    python run_simulation.py config.json
    -- or --
    from run_simulation import run_from_config
    results = run_from_config(config_dict)
"""

import sys, json, numpy as np, pandas as pd
from pathlib import Path

# Ensure all sibling modules (cover_excel, soil, vege etc.) are importable
# regardless of how this file is loaded.
_here = Path(__file__).resolve().parent
for _p in [str(_here), str(Path.cwd().resolve())]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from silo_fetch   import fetch_silo
from soil         import read_prm, init_sw
from vege         import read_vege, get_vege_state
# cover_excel imported lazily inside _make_cover_fn to avoid path issues
from waterbalance import daily_water_balance


# ── helpers ────────────────────────────────────────────────────────────────

def _interp(doys, vals, doy):
    """Simple linear interpolation over a DOY schedule."""
    return float(np.interp(doy, doys, vals))


def _run_daily(met_df, profile, get_state_fn):
    """
    Core daily loop.
    get_state_fn(doy) -> (green_cover_frac, total_cover_frac, root_depth_mm)
    Returns daily results DataFrame with mass-balance verified.
    """
    layers   = profile.layers
    sw       = init_sw(profile, 0.5)
    sw0      = sw.sum()
    sumes1   = sumes2 = t_since_wet = 0.0
    ll_total = sum(l.ll_mm for l in layers)   # wilting point total (mm)
    records  = []

    # Yield accumulation — season transpiration resets each year
    season_transp = 0.0   # mm accumulated since green cover appeared
    in_season     = False
    prev_green    = 0.0
    annual_yield  = {}    # year -> t/ha

    for date, row in met_df.iterrows():
        rain = float(row.get('rain', 0) or 0)
        epan = float(row.get('epan', 0) or 0)
        if np.isnan(rain): rain = 0.0
        if np.isnan(epan): epan = 0.0
        doy = int(row['doy'])

        green, total, root_depth = get_state_fn(doy)

        out = daily_water_balance(
            sw=sw, layers=layers, soil=profile,
            rain=rain, epan=epan,
            green_cover=green, total_cover=total,
            root_depth_mm=root_depth, crop_factor=1.0,
            sumes1=sumes1, sumes2=sumes2, t_since_wet=t_since_wet,
        )
        sw          = out['sw']
        sumes1      = out['sumes1']
        sumes2      = out['sumes2']
        t_since_wet = out['t_since_wet']

        # Plant available soil water = sum over all layers of (sw - ll), floored at 0
        # Computed layer-by-layer so each layer is independently clamped
        pasw = sum(max(0.0, float(out['sw'][i]) - layers[i].ll_mm)
                   for i in range(len(layers)))

        # Cover: green = living canopy %, residue = total - green (both as %)
        green_pct   = round(green * 100.0, 1)
        residue_pct = round(max(0.0, total - green) * 100.0, 1)

        # Yield: accumulate transpiration while green cover > 0
        # On the day green drops to zero, compute and record yield for that day
        year = date.year
        day_yield = 0.0
        if green > 0.01:
            in_season = True
            season_transp += float(out['transp'])
        elif in_season and prev_green > 0.01:
            # Green cover just dropped to zero — this IS the harvest day
            wue = getattr(get_state_fn, '_wue', 0.0)
            hi  = getattr(get_state_fn, '_hi',  0.0)
            if wue > 0 and hi > 0:
                biomass_t_ha = season_transp * wue / 1000.0   # g/m2 -> t/ha
                day_yield    = round(biomass_t_ha * hi, 3)
            annual_yield[year] = day_yield
            season_transp = 0.0
            in_season     = False
        prev_green = green
        records.append({
            'date'       : date,
            'rain'       : rain,
            'runoff'     : out['runoff'],
            'soil_evap'  : out['soil_evap'],
            'transp'     : out['transp'],
            'drainage'   : out['drainage'],
            'erosion'    : out['sediment'],
            'pasw'       : round(pasw, 2),
            'green_cover': green_pct,
            'residue_cover': residue_pct,
            'root_depth': round(root_depth, 1),
            'yield'     : day_yield,
            # kept for internal use (balance check, monthly summaries)
            'epan'     : epan,
            'et'       : out['et'],
            'sediment' : out['sediment'],
            'sw_total' : out['sw_total'],
        })

    df       = pd.DataFrame(records).set_index('date')
    sw_final = df['sw_total'].iloc[-1]
    # Handle any open season at end of record (crop still green on last day)
    if in_season and season_transp > 0:
        wue = getattr(get_state_fn, '_wue', 0.0)
        hi  = getattr(get_state_fn, '_hi',  0.0)
        if wue > 0 and hi > 0:
            biomass_t_ha = season_transp * wue / 1000.0
            end_yield    = round(biomass_t_ha * hi, 3)
            annual_yield[df.index[-1].year] = end_yield
            df.at[df.index[-1], 'yield'] = end_yield
    df.attrs['annual_yield'] = annual_yield
    return df, sw0, sw_final


def save_daily_csv(df, out_path):
    """
    Write the daily water balance output to CSV.

    Columns written:
        date           YYYY-MM-DD
        rain           Rainfall (mm)
        runoff         Surface runoff (mm)
        soil_evap      Soil evaporation (mm)
        transp         Transpiration (mm)
        drainage       Deep drainage below profile (mm)
        erosion        Sediment yield (t/ha)
        pasw           Plant available soil water, total profile (mm above wilting point)
        green_cover    Green (living) canopy cover (%)
        residue_cover  Surface residue cover (%)
    """
    from pathlib import Path as _Path
    out_path = _Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cols = ['rain', 'runoff', 'soil_evap', 'transp', 'drainage', 'erosion',
            'pasw', 'green_cover', 'residue_cover', 'root_depth', 'yield']
    # Only include columns that exist (guard against old df without cover cols)
    cols = [c for c in cols if c in df.columns]
    out  = df[cols].copy()
    out.index.name = 'date'
    out = out.round(3)

    out.to_csv(out_path)
    print(f"  Saved daily output : {out_path}  ({len(out):,} rows)")


def yield_series(df):
    """
    Extract annual yield (t/ha) from df.attrs into a pandas Series
    aligned by year, for use in charts and tables.
    Returns Series indexed by year (int), or empty Series if no yield data.
    """
    yd = df.attrs.get('annual_yield', {})
    if not yd:
        return pd.Series(dtype=float)
    return pd.Series(yd).sort_index()


def _monthly_means(df, nyears):
    """Monthly totals averaged over all years."""
    mon = df.groupby(df.index.month).sum(numeric_only=True).div(nyears).round(1)
    # delta SW per month
    df2 = df.copy()
    df2['_year']  = df2.index.year
    df2['_month'] = df2.index.month
    sw_s = df2.groupby(['_year','_month'])['sw_total'].first().groupby('_month').mean()
    sw_e = df2.groupby(['_year','_month'])['sw_total'].last().groupby('_month').mean()
    mon['dsw'] = (sw_e - sw_s).round(1)
    return mon


def _annual_stats(df):
    ann = df.resample('YE').sum(numeric_only=True)
    ann.index = ann.index.year
    return ann


# ── vege/cover state function factories ───────────────────────────────────

def _make_vege_fn(vege_obj):
    """Returns a get_state(doy) function from a parsed .vege object."""
    def fn(doy):
        green, total, roots = get_vege_state(vege_obj, doy)
        return green, total, roots
    # Attach yield parameters so _run_daily can access them
    fn._wue  = float(vege_obj.water_use_effic)
    fn._hi   = float(vege_obj.harvest_index)
    fn._name = (vege_obj.name if isinstance(vege_obj.name, str)
                else "".join(vege_obj.name))
    return fn


def _make_cover_fn(cover_obj):
    """Returns a get_state(doy) function from a parsed Excel cover object."""
    from cover_excel import get_cover_state  # local import avoids module-level path issues
    def fn(doy):
        green, total, roots = get_cover_state(cover_obj, doy)
        return green, total, roots
    fn._wue  = float(getattr(cover_obj, "tue", 0.0))
    fn._hi   = float(getattr(cover_obj, "hi",  0.0))
    fn._name = cover_obj.name
    return fn


def _make_inline_fn(schedule):
    """
    Build a get_state(doy) function from an inline schedule list
    (as sent from the frontend: [{doy, green, total, roots}, ...])
    """
    doys   = np.array([p['doy']   for p in schedule])
    greens = np.array([p['green'] / 100.0 for p in schedule])
    totals = np.array([p['total'] / 100.0 for p in schedule])
    roots  = np.array([p['roots'] for p in schedule])

    def fn(doy):
        g = float(np.interp(doy, doys, greens))
        t = float(np.interp(doy, doys, totals))
        r = float(np.interp(doy, doys, roots))
        return np.clip(g,0,1), np.clip(t,0,1), max(0.0,r)
    return fn


def _make_soil_from_dict(soil_dict):
    """
    Build a SoilProfile object from the inline dict sent by the frontend.
    Mirrors the structure produced by soil.read_prm().
    """
    from soil import SoilProfile, SoilLayer

    raw_layers = soil_dict.get('layers', [])
    layers = []
    prev_depth = 0.0
    for l in raw_layers:
        depth = float(l.get('depth', 0))
        thick = float(l.get('thickness', depth - prev_depth))
        if thick <= 0:
            thick = depth - prev_depth
        ad  = float(l.get('airdry', 3)) / 100.0  if float(l.get('airdry',3)) > 1 else float(l.get('airdry',0.03))
        ll  = float(l.get('ll', 12))   / 100.0   if float(l.get('ll',12))   > 1 else float(l.get('ll',0.12))
        dul = float(l.get('dul', 22))  / 100.0   if float(l.get('dul',22))  > 1 else float(l.get('dul',0.22))
        sat = float(l.get('sat', 27))  / 100.0   if float(l.get('sat',27))  > 1 else float(l.get('sat',0.27))
        ks  = float(l.get('ksat', 5))
        layer = SoilLayer(
            depth_mm  = depth,
            thickness = thick,
            airdry    = ad,  ll=ll, dul=dul, sat=sat, ksat=ks,
            ll_mm     = ll  * thick,
            dul_mm    = dul * thick,
            sat_mm    = sat * thick,
            airdry_mm = ad  * thick,
            pawc      = (dul - ll) * thick,
        )
        layers.append(layer)
        prev_depth = depth

    profile = SoilProfile(
        name        = soil_dict.get('name', 'Unknown soil'),
        layers      = layers,
        cona        = float(soil_dict.get('cona', 4.0)),
        u           = float(soil_dict.get('u', 9.0)),
        cn2_bare    = float(soil_dict.get('cn2', 85.0)),
        cn_cover_reduction = 20.0,
        cn_tillage_max     = 0.0,
        cn_roughness_rain  = 0.0,
        musle_k     = 0.48, musle_p=1.0, slope_pct=3.0,
        slope_length=100.0, rill_ratio=1.0, bulk_density=1.55,
        cracking=False, crack_infil=10.0,
    )
    profile.total_depth = sum(l.thickness for l in layers)
    profile.pawc_total  = sum(l.pawc for l in layers)
    return profile


# ── main entry point ───────────────────────────────────────────────────────

def run_from_config(config):
    """
    Run a full simulation from a config dict.

    Config keys:
        station : {lat, lon, number (optional), name, source}
        soil    : {name, layers:[{depth,thickness,airdry,ll,dul,sat,ksat},...],
                   cona, u, cn2}   -- OR --  {fname} (path to .PRM file)
        vege    : {schedule:[{doy,green,total,roots},...], name, format}
                  -- OR -- {fname} (path to .vege or .xlsx file)
        start   : 'YYYYMMDD'
        end     : 'YYYYMMDD'
        email   : 'user@example.com'

    Returns dict with keys:
        monthly    : {rain, runoff, evap, transp, drain, dsw} each [12 floats]
        annual     : {mean, cv, min, max} per component
        balance    : {error_mm, error_mm_yr}
        meta       : {station, soil, vege, start, end, nyears, pawc}
    """

    # ── 1. Climate ────────────────────────────────────────────────────────
    stn     = config['station']
    lat     = float(stn['lat'])
    lon     = float(stn['lon'])
    start   = config.get('start', '19570101')
    end     = config.get('end',   '19981231')
    email   = config.get('email', 'test@test.com')
    cache   = f"/home/claude/perfect/cache/silo_{lat:.3f}_{lon:.3f}_{start}_{end}.csv"

    print(f"Fetching SILO: ({lat}, {lon}) {start}–{end}")
    _, met_df = fetch_silo(lat=lat, lon=lon, start=start, end=end,
                           email=email, cache_path=cache)
    nyears = met_df.index.year.nunique()
    print(f"  {len(met_df)} days, {nyears} years")

    # ── 2. Soil ───────────────────────────────────────────────────────────
    soil_cfg = config['soil']
    if 'fname' in soil_cfg and Path(soil_cfg['fname']).exists():
        profile = read_prm(soil_cfg['fname'])
    else:
        profile = _make_soil_from_dict(soil_cfg)
    print(f"Soil: {profile.name}  PAWC={profile.pawc_total:.0f} mm")

    # ── 3. Vegetation ─────────────────────────────────────────────────────
    vege_cfg = config['vege']
    if 'fname' in vege_cfg and Path(vege_cfg['fname']).exists():
        fname = vege_cfg['fname']
        if fname.lower().endswith('.vege'):
            vege_obj = read_vege(fname)
            get_state = _make_vege_fn(vege_obj)
        else:
            from cover_excel import read_cover_excel  # local import
            cover_obj = read_cover_excel(fname)
            get_state = _make_cover_fn(cover_obj)
    elif 'schedule' in vege_cfg:
        get_state = _make_inline_fn(vege_cfg['schedule'])
    else:
        # bare fallow fallback
        get_state = lambda doy: (0.0, 0.0, 0.0)
    print(f"Vege: {vege_cfg.get('name','(inline schedule)')}")

    # ── 4. Run ────────────────────────────────────────────────────────────
    print("Running daily water balance…")
    df, sw0, sw_final = _run_daily(met_df, profile, get_state)
    dsw_total = sw_final - sw0
    print(f"Done. SW start={sw0:.1f}  end={sw_final:.1f}  ΔSW={dsw_total:.1f}")

    # ── 5. Balance check ──────────────────────────────────────────────────
    rain_t  = df['rain'].sum()
    ro_t    = df['runoff'].sum()
    dr_t    = df['drainage'].sum()
    ev_t    = df['soil_evap'].sum()
    tr_t    = df['transp'].sum()
    err     = rain_t - ro_t - dr_t - ev_t - tr_t - dsw_total
    print(f"Balance error: {err:.3f} mm over {nyears} years ({err/nyears:.4f} mm/yr)")

    # ── 6. Monthly means ──────────────────────────────────────────────────
    mon = _monthly_means(df, nyears)
    ann = _annual_stats(df)

    def to_list(col): return mon[col].tolist() if col in mon.columns else [0]*12

    results = {
        'monthly': {
            'rain'  : to_list('rain'),
            'runoff': to_list('runoff'),
            'evap'  : to_list('soil_evap'),
            'transp': to_list('transp'),
            'drain' : to_list('drainage'),
            'dsw'   : to_list('dsw'),
        },
        'annual': {
            'rain_mean'  : round(float(ann['rain'].mean()),   1),
            'rain_cv'    : round(float(ann['rain'].std()/ann['rain'].mean()*100), 0),
            'runoff_mean': round(float(ann['runoff'].mean()), 1),
            'drain_mean' : round(float(ann['drainage'].mean()),1),
            'et_mean'    : round(float(ann['et'].mean()),     1),
            'transp_mean': round(float(ann['transp'].mean()), 1),
        },
        'balance': {
            'sw_start_mm'  : round(sw0,     1),
            'sw_end_mm'    : round(sw_final, 1),
            'dsw_total_mm' : round(dsw_total,1),
            'error_mm'     : round(err,      3),
            'error_mm_yr'  : round(err/nyears,4),
        },
        'meta': {
            'station' : stn.get('name','Unknown'),
            'lat'     : lat,
            'lon'     : lon,
            'soil'    : profile.name,
            'vege'    : vege_cfg.get('name',''),
            'start'   : start,
            'end'     : end,
            'nyears'  : nyears,
            'pawc_mm' : round(profile.pawc_total, 1),
        },
    }

    # ── 7. Optional daily CSV output ─────────────────────────────────────
    daily_csv = config.get('daily_csv')
    if daily_csv:
        save_daily_csv(df, daily_csv)

    return results


# ── CLI ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if len(sys.argv) < 2:
        # quick test with known-good inputs
        config = {
            'station'  : {'name':'Dalby','lat':-27.28,'lon':151.26,'source':'DataDrill'},
            'soil'     : {'fname':'/mnt/user-data/uploads/AVERRBE.PRM'},
            'vege'     : {'fname':'/mnt/user-data/uploads/wheat_stubble_incorporated.vege'},
            'start'    : '19570101',
            'end'      : '19981231',
            'email'    : 'test@test.com',
            'daily_csv': 'Dalby_daily.csv',
        }
    else:
        with open(sys.argv[1]) as f:
            config = json.load(f)
        # Auto-generate daily CSV path if not specified in config
        if 'daily_csv' not in config:
            stn   = config.get('station', {}).get('name', 'run')
            start = config.get('start', '')[:4]
            end   = config.get('end',   '')[:4]
            config['daily_csv'] = f"{stn}_{start}_{end}_daily.csv"

    results = run_from_config(config)
    print(json.dumps(results, indent=2))
