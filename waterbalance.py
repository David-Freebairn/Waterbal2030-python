"""
PERFECT model — daily soil water balance engine

Implements the key hydrological processes in order:
  1. Runoff          (SCS curve number method)
  2. Infiltration    (rainfall - runoff, distributed to layers)
  3. Drainage        (cascade: excess above DUL drains to layer below)
  4. Soil evaporation (two-stage: Ritchie model)
  5. Transpiration   (limited by potential ET and root water uptake)
  6. Deep drainage   (water draining below bottom layer)

References:
  Littleboy et al. (1992) PERFECT v2.0 manual, DAQ
  Ritchie (1972) two-stage soil evaporation
  SCS (1972) curve number runoff
"""

import numpy as np


# ---------------------------------------------------------------------------
# 1. Runoff — SCS curve number
# ---------------------------------------------------------------------------

def calc_cn(cn2, cover_frac, cn_cover_reduction, tillage_reduction=0.0):
    """
    Adjust CN2 for surface cover and tillage, then return CN1/CN2/CN3
    and the effective CN for current conditions.

    cover_frac              : 0–1 fractional ground cover
    cn_cover_reduction      : max CN reduction at 100% cover
    """
    cn2_adj = cn2 - cover_frac * cn_cover_reduction - tillage_reduction
    cn2_adj = np.clip(cn2_adj, 1.0, 99.0)
    # AMC-I and AMC-III from CN2
    cn1 = cn2_adj / (2.383 - 0.0123 * cn2_adj)
    cn3 = cn2_adj * np.exp(0.00673 * (100.0 - cn2_adj))
    return cn1, cn2_adj, cn3


def calc_runoff(rain_mm, cn2, cover_frac, cn_cover_reduction,
                tillage_reduction=0.0, sw_ratio=None):
    """
    SCS-CN runoff for a single day.

    sw_ratio : float or None
        Antecedent moisture condition — ratio of current available water
        to PAWC, i.e. (sw_total - ll_total) / (dul_total - ll_total).
        Range 0 (dry, at WP) to 1 (full, at DUL); values >1 possible
        if profile is above DUL.
        If None, uses fixed CN2 (original PERFECT behaviour).
        If provided, interpolates between CN1 (dry) and CN3 (wet) based
        on soil wetness — the standard HowLeaky/PERFECT v3 AMC approach.

    Returns runoff (mm).
    """
    if rain_mm <= 0:
        return 0.0

    cn1, cn2_eff, cn3 = calc_cn(cn2, cover_frac, cn_cover_reduction,
                                  tillage_reduction)

    if sw_ratio is not None:
        # AMC adjustment: interpolate CN between CN1 (dry) and CN3 (wet)
        r = max(0.0, min(1.0, sw_ratio))
        cn_eff = cn1 + r * (cn3 - cn1)
    else:
        cn_eff = cn2_eff

    s  = 254.0 * (100.0 / cn_eff - 1.0)   # potential maximum retention (mm)
    ia = 0.2 * s                             # initial abstraction
    if rain_mm <= ia:
        return 0.0
    runoff = (rain_mm - ia) ** 2 / (rain_mm - ia + s)
    return max(0.0, runoff)


# ---------------------------------------------------------------------------
# 2. Infiltration and redistribution
# ---------------------------------------------------------------------------

def infiltrate_and_drain(sw, layers, infil_mm):
    """
    Add infiltration to the soil profile and cascade excess water downward.

    sw      : np.array of current soil water (mm) per layer
    layers  : list of SoilLayer objects
    infil_mm: water entering top of profile (mm)

    Returns updated sw array and deep_drain (mm leaving bottom layer).
    """
    sw = sw.copy()
    deep_drain = 0.0
    input_mm = infil_mm

    for i, layer in enumerate(layers):
        sw[i] += input_mm
        # Excess above saturation becomes surface ponding/runoff (handled upstream)
        # Excess above DUL drains to next layer within the day
        if sw[i] > layer.dul_mm:
            drain = sw[i] - layer.dul_mm
            # Limit by Ksat (convert mm/hr to mm/day, cap at excess)
            ksat_day = layer.ksat * 24.0
            drain = min(drain, ksat_day)
            sw[i] -= drain
            input_mm = drain
        else:
            input_mm = 0.0

    # Any drainage from the bottom layer is deep drainage
    deep_drain = input_mm
    # Enforce physical bounds
    for i, layer in enumerate(layers):
        sw[i] = np.clip(sw[i], layer.airdry_mm, layer.sat_mm)

    return sw, deep_drain


# ---------------------------------------------------------------------------
# 3. Soil evaporation — Ritchie two-stage model
# ---------------------------------------------------------------------------

def calc_soil_evap(sw, layers, eos, u, cona, sumes1, sumes2, t_since_wet):
    """
    Ritchie two-stage soil evaporation.

    eos          : potential soil evaporation (mm/day)
    u            : stage-I limit (mm)
    cona         : stage-II coefficient (mm/day^0.5)
    sumes1       : cumulative stage-I evaporation since last wetting
    sumes2       : cumulative stage-II evaporation since last wetting
    t_since_wet  : days since last significant wetting event

    Returns (es, sumes1, sumes2, t_since_wet) where es is actual soil evap (mm).
    """
    if eos <= 0:
        return 0.0, sumes1, sumes2, t_since_wet

    # Stage I: evaporation limited only by supply (up to U mm cumulative)
    if sumes1 < u:
        es1 = min(eos, u - sumes1)
        sumes1 += es1
        es = es1
        if sumes1 >= u:
            # Transition to stage II — reset day counter
            t_since_wet = 0.0
        return es, sumes1, sumes2, t_since_wet

    # Stage II: evaporation proportional to sqrt(t)
    t_since_wet += 1.0
    es2_potential = cona * (t_since_wet ** 0.5 - (t_since_wet - 1.0) ** 0.5)
    es2 = min(eos, es2_potential)

    # Limit by water available in top layer above air-dry — BEFORE updating accumulator
    avail_top = max(0.0, sw[0] - layers[0].airdry_mm)
    es2 = min(es2, avail_top)

    # Only accumulate what was actually evaporated
    sumes2 += es2
    es = es2

    return es, sumes1, sumes2, t_since_wet


def reset_evap_accumulators(rain_mm, sumes1, sumes2, t_since_wet, u):
    """
    Reset evaporation stage accumulators after a wetting event.
    PERFECT resets when daily rain > 10 mm (approximate threshold).
    """
    if rain_mm >= 10.0:
        sumes1 = 0.0
        sumes2 = 0.0
        t_since_wet = 0.0
    return sumes1, sumes2, t_since_wet


# ---------------------------------------------------------------------------
# 4. Transpiration / root water extraction
# ---------------------------------------------------------------------------

def calc_transpiration(sw, layers, ep, root_depth_mm):
    """
    Extract transpiration water from rooted layers proportional to
    plant available water in each layer.

    ep           : potential transpiration (mm/day)
    root_depth_mm: current rooting depth

    Returns (actual_transp, updated sw).
    """
    sw = sw.copy()
    if ep <= 0 or root_depth_mm <= 0:
        return 0.0, sw

    # Determine which layers are within rooting depth
    cum_depth = 0.0
    avail = []
    root_fracs = []  # fraction of layer within root zone
    for idx, layer in enumerate(layers):
        cum_depth_prev = cum_depth
        cum_depth += layer.thickness
        if cum_depth_prev >= root_depth_mm:
            avail.append(0.0)
            root_fracs.append(0.0)
        else:
            root_frac = min(1.0, (root_depth_mm - cum_depth_prev) / layer.thickness)
            root_fracs.append(root_frac)
            # Ensure non-negative — sw[idx] may be at ll_mm already
            avail.append(max(0.0, sw[idx] - layer.ll_mm) * root_frac)

    total_avail = sum(avail)
    if total_avail <= 0:
        return 0.0, sw

    # Actual transpiration limited by availability
    transp = min(ep, total_avail)

    # Extract proportionally from each layer, track what was actually removed
    actual_transp = 0.0
    for i, (av, rf) in enumerate(zip(avail, root_fracs)):
        if av > 0 and total_avail > 0:
            extract = transp * (av / total_avail)
            sw_before = sw[i]
            sw[i] = max(sw[i] - extract, layers[i].ll_mm)
            actual_transp += sw_before - sw[i]

    return max(0.0, actual_transp), sw


# ---------------------------------------------------------------------------
# 5. Potential ET partitioning
# ---------------------------------------------------------------------------

def partition_et(epan, green_cover, crop_factor=1.0):
    """
    Split pan evaporation into potential soil evaporation (eos)
    and potential transpiration (ep).

    green_cover : fraction of ground covered by GREEN (living) canopy
                  — drives radiation interception and transpiration demand
    crop_factor : scales total PET (default 1.0)

    Soil evap is reduced under the canopy (Beer's law approximation).
    Transpiration demand is proportional to green cover fraction.
    """
    pet = epan * crop_factor
    eos = pet * (1.0 - green_cover)
    ep  = pet * green_cover
    return eos, ep



# ---------------------------------------------------------------------------
# 7. Erosion — PERFECT sediment concentration model
# ---------------------------------------------------------------------------

def calc_ls_factor(slope_pct, slope_length_m, rill_ratio=1.0):
    """
    Compute the USLE LS (slope length-gradient) factor.

    Uses the McCool et al. (1987) equations as implemented in PERFECT:
      S  = sin(theta) based
      L  = (slope_length / 22.13) ^ m
      m  = 0.6 for slopes > 5%, 0.5 for 3-5%, 0.4 for 1-3%, 0.3 for < 1%

    rill_ratio adjusts for rill vs interrill contribution.
    """
    import math
    theta = math.atan(slope_pct / 100.0)
    sin_t = math.sin(theta)

    # S factor (McCool steep-slope equation)
    if slope_pct >= 9.0:
        s_factor = 16.8 * sin_t - 0.50
    else:
        s_factor = 10.8 * sin_t + 0.03

    # L factor exponent m based on slope
    if slope_pct > 5.0:
        m = 0.6
    elif slope_pct >= 3.0:
        m = 0.5
    elif slope_pct >= 1.0:
        m = 0.4
    else:
        m = 0.3

    l_factor = (slope_length_m / 22.13) ** m
    return l_factor * s_factor * rill_ratio


def calc_erosion(runoff_mm, total_cover_frac, ls_factor, kusle, pusle):
    """
    PERFECT daily sediment yield (t/ha).

    Directly translates the Fortran erosion subroutine:

        sed = 0
        if runf <= 1: return
        cover = min(100, (covm + ccov) * 100)          # total cover %
        if cover < 50: conc = 16.52 - 0.46*cover + 0.0031*cover^2
        if cover >= 50: conc = -0.0254*cover + 2.54
        conc = max(0, conc)
        sed = conc * ls * kusle * pusle * runf / 10

    Parameters
    ----------
    runoff_mm        : float  daily runoff (mm)
    total_cover_frac : float  total ground cover fraction 0–1 (green + residue)
    ls_factor        : float  pre-computed LS factor for the site
    kusle            : float  soil erodibility K factor
    pusle            : float  support practice P factor

    Returns
    -------
    sed : float  sediment yield (t/ha/day), 0 if runoff <= 1 mm
    """
    if runoff_mm <= 1.0:
        return 0.0

    cover = min(100.0, total_cover_frac * 100.0)

    if cover < 50.0:
        conc = 16.52 - 0.46 * cover + 0.0031 * cover * cover
    else:
        conc = -0.0254 * cover + 2.54

    conc = max(0.0, conc)
    sed = conc * ls_factor * kusle * pusle * runoff_mm / 10.0
    return sed

# ---------------------------------------------------------------------------
# 6. Main daily step
# ---------------------------------------------------------------------------

def daily_water_balance(
        sw, layers, soil,
        rain, epan,
        green_cover, total_cover, root_depth_mm, crop_factor,
        sumes1, sumes2, t_since_wet,
        tillage_cn_reduction=0.0
    ):
    """
    Run one day of the PERFECT soil water balance.

    Parameters
    ----------
    sw              : np.array  soil water per layer (mm)
    layers          : list of SoilLayer
    soil            : SoilProfile (holds CN, Cona, U etc.)
    rain            : float  daily rainfall (mm)
    epan            : float  pan evaporation (mm)
    green_cover     : float  green (living) canopy cover fraction (0–1)
                             — used for ET partitioning
    total_cover     : float  total ground cover fraction (green + residue, 0–1)
                             — used for runoff CN reduction
    root_depth_mm   : float  current rooting depth (mm)
    crop_factor     : float  ET crop factor (1.0 = reference pan)
    sumes1/2        : floats  accumulated soil evap stage I/II (mm)
    t_since_wet     : float  days since last wetting (for stage II)
    tillage_cn_reduction : float  CN reduction from recent tillage

    Returns
    -------
    dict of daily fluxes + updated state variables
    """

    # -- 1. Runoff — uses TOTAL cover (green + residue) -----------------------
    # Antecedent moisture condition: how full is the profile relative to PAWC?
    ll_total  = sum(l.ll_mm  for l in layers)
    dul_total = sum(l.dul_mm for l in layers)
    pawc_eff  = dul_total - ll_total
    sw_ratio  = (sw.sum() - ll_total) / pawc_eff if pawc_eff > 0 else 0.5
    runoff = calc_runoff(rain, soil.cn2_bare, total_cover,
                         soil.cn_cover_reduction, tillage_cn_reduction,
                         sw_ratio=sw_ratio)
    infil = max(0.0, rain - runoff)

    # -- 2. Reset evap accumulators if significant rain -----------------------
    sumes1, sumes2, t_since_wet = reset_evap_accumulators(
        rain, sumes1, sumes2, t_since_wet, soil.u)

    # -- 3. Infiltrate and drain ----------------------------------------------
    sw, deep_drain = infiltrate_and_drain(sw, layers, infil)

    # -- 4. Partition ET — uses GREEN cover for transpiration demand ----------
    eos, ep = partition_et(epan, green_cover, crop_factor)

    # -- 5. Soil evaporation --------------------------------------------------
    es, sumes1, sumes2, t_since_wet = calc_soil_evap(
        sw, layers, eos, soil.u, soil.cona, sumes1, sumes2, t_since_wet)
    sw[0] = max(sw[0] - es, layers[0].airdry_mm)

    # -- 6. Transpiration -----------------------------------------------------
    transp, sw = calc_transpiration(sw, layers, ep, root_depth_mm)

    # -- Summary water balance check ------------------------------------------
    total_sw = sw.sum()

    # -- 7. Erosion -----------------------------------------------------------
    ls  = calc_ls_factor(soil.slope_pct, soil.slope_length, soil.rill_ratio)
    sed = calc_erosion(runoff, total_cover, ls, soil.musle_k, soil.musle_p)

    return {
        'sw'          : sw,
        'sw_total'    : total_sw,
        'runoff'      : runoff,
        'infil'       : infil,
        'drainage'    : deep_drain,
        'soil_evap'   : es,
        'transp'      : transp,
        'et'          : es + transp,
        'sediment'    : sed,
        'sumes1'      : sumes1,
        'sumes2'      : sumes2,
        't_since_wet' : t_since_wet,
    }


# ---------------------------------------------------------------------------
# Convenience: run full simulation over a climate DataFrame
# ---------------------------------------------------------------------------

def run_simulation(met_df, profile, cover_frac=0.0, root_depth_mm=300.0,
                   crop_factor=1.0, sw_init_frac=0.5):
    """
    Run a multi-year daily water balance simulation.

    met_df      : DataFrame from read_met() or fetch_silo()
    profile     : SoilProfile from read_prm()
    cover_frac  : constant fractional cover — used as BOTH green and total
                  (appropriate for bare fallow or simple uniform cover)
    root_depth  : constant root depth (mm)
    crop_factor : ET scaling factor
    sw_init_frac: initial SW as fraction of PAWC above LL

    Returns a DataFrame of daily outputs.
    """
    from soil import init_sw
    import pandas as pd

    layers = profile.layers
    sw = init_sw(profile, sw_init_frac)

    sumes1, sumes2, t_since_wet = 0.0, 0.0, 0.0

    records = []
    for date, row in met_df.iterrows():
        rain = row.get('rain', 0.0)
        epan = row.get('epan', 0.0)
        if np.isnan(rain): rain = 0.0
        if np.isnan(epan): epan = 0.0

        out = daily_water_balance(
            sw=sw, layers=layers, soil=profile,
            rain=rain, epan=epan,
            green_cover=cover_frac,   # same for simple bare/uniform scenarios
            total_cover=cover_frac,
            root_depth_mm=root_depth_mm,
            crop_factor=crop_factor,
            sumes1=sumes1, sumes2=sumes2,
            t_since_wet=t_since_wet,
        )

        sw           = out['sw']
        sumes1       = out['sumes1']
        sumes2       = out['sumes2']
        t_since_wet  = out['t_since_wet']

        rec = {
            'date'      : date,
            'rain'      : rain,
            'epan'      : epan,
            'runoff'    : out['runoff'],
            'infil'     : out['infil'],
            'drainage'  : out['drainage'],
            'soil_evap' : out['soil_evap'],
            'transp'    : out['transp'],
            'et'        : out['et'],
            'sw_total'  : out['sw_total'],
        }
        # Per-layer SW
        for i, s in enumerate(sw):
            rec[f'sw_layer{i+1}'] = s

        records.append(rec)

    df = pd.DataFrame(records).set_index('date')
    return df
