"""
HowLeaky .soil XML file parser
Handles the multi-value attribute format:
  <LayerDepth Count="4" value1="100" value2="300" value3="900" value4="1500" Units="mm"/>

All layer properties are stored as value1..valueN attributes on a single tag.
Scalar parameters (Cona, U, CN2 etc.) are stored as text content of their tags.
"""

import xml.etree.ElementTree as ET
import numpy as np
from pathlib import Path
from soil import SoilProfile, SoilLayer


def _get_values(st, tag, n):
    """Extract value1..valueN float list from a tag's attributes."""
    el = st.find(tag)
    if el is None:
        return [0.0] * n
    return [float(el.get(f'value{i+1}', 0)) for i in range(n)]


def _get_scalar(st, *tags, default=0.0):
    """Get text content of the first matching tag."""
    for tag in tags:
        el = st.find(tag)
        if el is not None and el.text:
            try:
                return float(el.text.strip())
            except ValueError:
                pass
    return default


def read_soil_xml(filepath):
    """
    Parse a HowLeaky .soil XML file into a SoilProfile object.

    Handles the multi-value attribute format used by HowLeaky:
      - LayerDepth, WiltingPoint, FieldCapacity etc. stored as value1..valueN
      - MaxDailyDrainRate (mm/day) used in place of Ksat
      - Scalar params (Cona, U, CN2) stored as element text
    """
    filepath = Path(filepath)
    tree = ET.parse(filepath)
    root = tree.getroot()
    st = root.find('SoilType')
    if st is None:
        raise ValueError(f"No <SoilType> element found in {filepath}")

    name = st.get('text') or st.get('Description') or filepath.stem
    n = int(_get_scalar(st, 'HorizonCount', default=4))

    # Layer arrays
    depths   = _get_values(st, 'LayerDepth',        n)   # mm cumulative
    airdry   = _get_values(st, 'InSituAirDryMoist',  n)   # %vol
    ll       = _get_values(st, 'WiltingPoint',        n)   # %vol
    dul      = _get_values(st, 'FieldCapacity',       n)   # %vol
    sat      = _get_values(st, 'SatWaterCont',        n)   # %vol
    drain_d  = _get_values(st, 'MaxDailyDrainRate',   n)   # mm/day
    bulk_d   = _get_values(st, 'BulkDensity',          n)   # g/cm3

    # Build SoilLayer objects
    layers = []
    prev_depth = 0.0
    for i in range(n):
        depth = depths[i]
        thick = depth - prev_depth
        ad  = airdry[i] / 100.0
        l   = ll[i]     / 100.0
        d   = dul[i]    / 100.0
        s   = sat[i]    / 100.0
        # Convert MaxDailyDrainRate (mm/day) → Ksat (mm/hr) for compatibility
        ksat = drain_d[i] / 24.0

        layer = SoilLayer(
            depth_mm     = depth,
            thickness    = thick,
            airdry       = ad,
            ll           = l,
            dul          = d,
            sat          = s,
            ksat         = ksat,
            ll_mm        = l * thick,
            dul_mm       = d * thick,
            sat_mm       = s * thick,
            airdry_mm    = ad * thick,
            pawc         = (d - l) * thick,
            bulk_density = bulk_d[i],
        )
        layers.append(layer)
        prev_depth = depth

    # Scalar parameters
    cona  = _get_scalar(st, 'Stage2SoilEvap_Cona', default=4.0)
    u     = _get_scalar(st, 'Stage1SoilEvap_U',    default=9.0)
    cn2   = _get_scalar(st, 'RunoffCurveNumber',    default=85.0)
    cn_cv = _get_scalar(st, 'RedInCNAtFullCover',   default=20.0)
    cn_tl = _get_scalar(st, 'MaxRedInCNDueToTill',  default=0.0)
    cn_rn = _get_scalar(st, 'RainToRemoveRough',    default=0.0)
    k_fac = _get_scalar(st, 'USLE_K',               default=0.48)
    p_fac = _get_scalar(st, 'USLE_P',               default=1.0)
    slope = _get_scalar(st, 'FieldSlope',            default=3.0)
    sl    = _get_scalar(st, 'SlopeLength',           default=100.0)
    rill  = _get_scalar(st, 'RillRatio',             default=1.0)
    crack_el = st.find('SoilCrack')
    cracking = crack_el is not None and crack_el.get('state','false').lower() == 'true'
    crack_infil = _get_scalar(st, 'MaxInfiltIntoCracks', default=10.0)

    profile = SoilProfile(
        name                = name,
        layers              = layers,
        cona                = cona,
        u                   = u,
        cn2_bare            = cn2,
        cn_cover_reduction  = cn_cv,
        cn_tillage_max      = cn_tl,
        cn_roughness_rain   = cn_rn,
        musle_k             = k_fac,
        musle_p             = p_fac,
        slope_pct           = slope,
        slope_length        = sl,
        rill_ratio          = rill,
        bulk_density        = sum(bulk_d) / len(bulk_d),  # mean, kept for compat
        cracking            = cracking,
        crack_infil         = crack_infil,
    )
    profile.total_depth = depths[-1]
    profile.pawc_total  = sum(l.pawc for l in layers)
    return profile


if __name__ == '__main__':
    p = read_soil_xml('/mnt/user-data/uploads/Black_earth_4_layer.soil')
    print(f"Soil   : {p.name}")
    print(f"Layers : {len(p.layers)}   Depth: {p.total_depth:.0f} mm   PAWC: {p.pawc_total:.0f} mm")
    print(f"CN2={p.cn2_bare}  CN cover reduction={p.cn_cover_reduction}  Cona={p.cona}  U={p.u}")
    print()
    print(f"{'Lyr':>4}  {'Thick':>6}  {'AirDry':>7}  {'LL':>6}  {'DUL':>6}  {'SAT':>6}  {'Ksat':>8}  {'PAWC':>6}")
    for i,l in enumerate(p.layers):
        print(f"  {i+1:2d}  {l.thickness:6.0f}  {l.airdry*100:6.1f}%  {l.ll*100:5.1f}%  {l.dul*100:5.1f}%  {l.sat*100:5.1f}%  {l.ksat:6.2f}mm/hr  {l.pawc:5.1f}mm")
    print(f"\n  Total PAWC: {p.pawc_total:.0f} mm  (file says 288 mm)")
