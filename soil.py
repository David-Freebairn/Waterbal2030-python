"""
PERFECT model — soil profile reader and initialisation
Parses .PRM files and sets up layer-by-layer water content arrays.
"""

import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import List


@dataclass
class SoilLayer:
    """One soil horizon."""
    depth_mm   : float   # cumulative depth to bottom of layer
    thickness  : float   # layer thickness (mm)  — derived
    airdry     : float   # air-dry water content (%vol → fraction)
    ll         : float   # lower limit / wilting point (fraction)
    dul        : float   # drained upper limit / field capacity (fraction)
    sat        : float   # saturation (fraction)
    ksat       : float   # saturated hydraulic conductivity (mm/hr)
    # derived
    ll_mm      : float = 0.0   # ll in mm water
    dul_mm     : float = 0.0   # dul in mm water
    sat_mm     : float = 0.0   # sat in mm water
    airdry_mm  : float = 0.0
    pawc         : float = 0.0   # plant available water capacity (mm)
    bulk_density : float = 1.4   # bulk density (g/cm3)


@dataclass
class SoilProfile:
    name        : str
    layers      : List[SoilLayer]
    cona        : float   # stage-II evap coefficient (mm/day^0.5)
    u           : float   # stage-I evap limit (mm)
    cn2_bare    : float   # curve number, bare soil AMC-II
    cn_cover_reduction : float  # CN reduction at 100% cover
    cn_tillage_max : float
    cn_roughness_rain : float
    musle_k     : float
    musle_p     : float
    slope_pct   : float
    slope_length: float
    rill_ratio  : float
    bulk_density: float
    cracking    : bool
    crack_infil : float   # max infiltration via cracks (mm)

    # computed
    total_depth : float = 0.0
    pawc_total  : float = 0.0


def read_prm(filepath):
    """Parse a PERFECT .PRM soil parameter file."""
    lines = [l.rstrip() for l in open(filepath, encoding='utf-8', errors='replace')]

    name = lines[0].strip()
    # Skip separator lines (---) to find data
    data_lines = [l for l in lines if not l.startswith('-') and l.strip()]

    # n horizons is first numeric line after name
    n_horizons = int(data_lines[1].split()[0])

    # Find horizon data lines — they start with a float (depth)
    horizon_lines = []
    for l in data_lines[2:]:
        parts = l.split()
        if len(parts) >= 6:
            try:
                float(parts[0]); float(parts[1]); float(parts[2])
                horizon_lines.append(parts)
                if len(horizon_lines) == n_horizons:
                    break
            except ValueError:
                continue

    layers = []
    prev_depth = 0.0
    for p in horizon_lines:
        depth = float(p[0])
        thick = depth - prev_depth
        ad  = float(p[1]) / 100.0
        ll  = float(p[2]) / 100.0
        dul = float(p[3]) / 100.0
        sat = float(p[4]) / 100.0
        ks  = float(p[5])
        layer = SoilLayer(
            depth_mm  = depth,
            thickness = thick,
            airdry    = ad,
            ll        = ll,
            dul       = dul,
            sat       = sat,
            ksat      = ks,
            ll_mm     = ll  * thick,
            dul_mm    = dul * thick,
            sat_mm    = sat * thick,
            airdry_mm = ad  * thick,
            pawc      = (dul - ll) * thick,
        )
        layers.append(layer)
        prev_depth = depth

    # Scalar parameters — read in order after horizon block
    # Find them by scanning for lines with a leading float
    scalar_lines = []
    in_horizons = False
    found_horizons = 0
    for l in data_lines[2:]:
        parts = l.split()
        if not parts:
            continue
        try:
            float(parts[0])
            if found_horizons < n_horizons:
                found_horizons += 1
            else:
                scalar_lines.append(float(parts[0]))
        except ValueError:
            continue

    (cona, u, cn2_bare, cn_cov, cn_till, cn_rain,
     musle_k, musle_p, slope_pct, slope_len, rill,
     bulk_density) = scalar_lines[:12]

    # Cracking
    crack_line = [l for l in data_lines if l.strip().lower().startswith(('y','n')) and
                  'crack' not in l.lower()[:2]]
    cracking_line = [l for l in lines if 'crack' in l.lower() and
                     l.strip()[0].lower() in ('y','n')]
    cracking = False
    crack_infil = float(scalar_lines[12]) if len(scalar_lines) > 12 else 10.0
    for l in lines:
        stripped = l.strip().lower()
        if stripped.startswith('y') and 'crack' in l.lower():
            cracking = True
        elif stripped.startswith('n') and 'crack' in l.lower():
            cracking = False

    profile = SoilProfile(
        name        = name,
        layers      = layers,
        cona        = cona,
        u           = u,
        cn2_bare    = cn2_bare,
        cn_cover_reduction = cn_cov,
        cn_tillage_max = cn_till,
        cn_roughness_rain = cn_rain,
        musle_k     = musle_k,
        musle_p     = musle_p,
        slope_pct   = slope_pct,
        slope_length= slope_len,
        rill_ratio  = rill,
        bulk_density= bulk_density,
        cracking    = cracking,
        crack_infil = crack_infil,
    )
    profile.total_depth = sum(l.thickness for l in layers)
    profile.pawc_total  = sum(l.pawc for l in layers)
    return profile


def init_sw(profile, fraction=0.5):
    """
    Initialise soil water content for each layer.
    fraction=0.5 means halfway between LL and DUL.
    Returns array of SW (mm) per layer.
    """
    sw = np.array([
        l.ll_mm + fraction * l.pawc
        for l in profile.layers
    ])
    return sw


if __name__ == '__main__':
    p = read_prm('/mnt/user-data/uploads/AVERRBE.PRM')
    print(f"Soil: {p.name}")
    print(f"Layers: {len(p.layers)}   Total depth: {p.total_depth} mm   PAWC: {p.pawc_total:.1f} mm")
    print(f"CN2 bare: {p.cn2_bare}   Cona: {p.cona}   U: {p.u}")
    for i, l in enumerate(p.layers):
        print(f"  Layer {i+1}: {l.thickness:5.0f} mm thick  "
              f"LL={l.ll*100:.1f}%  DUL={l.dul*100:.1f}%  SAT={l.sat*100:.1f}%  "
              f"PAWC={l.pawc:.1f} mm")
    sw0 = init_sw(p)
    print(f"\nInitial SW (50% of PAWC): {sw0}  total={sw0.sum():.1f} mm")
