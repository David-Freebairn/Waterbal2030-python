"""
HowLeaky .vege format reader
Parses XML vegetation/crop files and provides daily cover, root depth,
and crop factor for use in the PERFECT-Python water balance engine.

CropFactorMatrix columns:
  x = day of year
  y = green cover (%)
  z = total cover / residue cover (%)  — used for runoff CN adjustment
  a = root depth (mm)

ModelType index=1 → ET/cover factor model (same science as PERFECT flag=4)
"""

import numpy as np
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VegeTemplate:
    name                : str
    model_type          : int       # 1 = ET/cover factor
    pan_plant_day       : int       # day of year for planting
    sw_prop_no_stress   : float     # SW proportion for no water stress (0–1)
    days_plant_harvest  : int       # days from planting to harvest
    cover_input_option  : int       # 0 = user-defined schedule
    water_use_effic     : float     # WUE (g/m2/mm transpiration)
    harvest_index       : float     # pan harvest index
    max_total_cover     : float     # cap on total cover fraction (0–1)
    # Cover/root schedule arrays (by DOY)
    doy          : np.ndarray       # day of year breakpoints
    green_cover  : np.ndarray       # green cover (fraction)
    total_cover  : np.ndarray       # total (green + residue) cover (fraction)
    root_depth   : np.ndarray       # root depth (mm)


def read_vege(filepath) -> VegeTemplate:
    """Parse a HowLeaky .vege XML file."""
    tree = ET.parse(filepath)
    root = tree.getroot()
    vt   = root.find('VegetationType')

    def text(tag, default=None):
        el = vt.find(tag)
        return el.text.strip() if el is not None and el.text else default

    def fval(tag, default=0.0):
        return float(text(tag, default))

    def ival(tag, default=0):
        return int(text(tag, default))

    name       = vt.get('text', Path(filepath).stem)
    model_type = int(vt.find('ModelType').get('index', 1))

    pan_plant_day      = ival('PanPlantDay')
    sw_prop            = fval('SWPropForNoStress')
    days_ph            = ival('DaysPlantingToHarvest')
    cover_opt          = int(vt.find('CoverInputOptions').get('index', 0))
    wue                = fval('WaterUseEffic')
    hi                 = fval('PanHarvestIndex')
    max_cover          = fval('MaxAllowTotalCover', 1.0)

    # Parse CropFactorMatrix
    matrix = vt.find('CropFactorMatrix')
    doys, greens, totals, roots = [], [], [], []
    for data in matrix.findall('Data'):
        doys.append(int(data.get('x')))
        greens.append(float(data.get('y')) / 100.0)
        totals.append(float(data.get('z')) / 100.0)
        roots.append(float(data.get('a')))

    return VegeTemplate(
        name               = name,
        model_type         = model_type,
        pan_plant_day      = pan_plant_day,
        sw_prop_no_stress  = sw_prop,
        days_plant_harvest = days_ph,
        cover_input_option = cover_opt,
        water_use_effic    = wue,
        harvest_index      = hi,
        max_total_cover    = max_cover,
        doy                = np.array(doys),
        green_cover        = np.array(greens),
        total_cover        = np.array(totals),
        root_depth         = np.array(roots),
    )


def get_vege_state(vege: VegeTemplate, doy: int):
    """
    Interpolate green cover (fraction), total cover (fraction),
    and root depth (mm) for a given day of year.
    Total cover uses the fractional cover model:
        total = green + (1 - green) * residue
    where residue = total_cover (from schedule) - green_cover.
    """
    green = float(np.interp(doy, vege.doy, vege.green_cover))
    total_sched = float(np.interp(doy, vege.doy, vege.total_cover))
    roots = float(np.interp(doy, vege.doy, vege.root_depth))

    green = np.clip(green, 0.0, vege.max_total_cover)
    # residue = schedule total minus green (floored at 0)
    residue = max(0.0, total_sched - green)
    # fractional cover model: residue covers only the bare fraction
    total = green + (1.0 - green) * residue
    total = np.clip(total, 0.0, vege.max_total_cover)
    roots = max(0.0, roots)
    return green, total, roots


if __name__ == '__main__':
    vege = read_vege('/mnt/user-data/uploads/wheat_stubble_incorporated.vege')
    print(f"Name              : {vege.name}")
    print(f"Model type        : {vege.model_type}")
    print(f"Planting DOY      : {vege.pan_plant_day}")
    print(f"Days to harvest   : {vege.days_plant_harvest}")
    print(f"WUE               : {vege.water_use_effic} g/m2/mm")
    print(f"Harvest index     : {vege.harvest_index}")
    print(f"Schedule points   : {len(vege.doy)}")
    print()
    print(f"{'Month':<8} {'DOY':>5} {'Green cover':>12} {'Total cover':>12} {'Root depth':>11}")
    print("-" * 52)
    month_doys = [15,46,74,105,135,152,166,196,228,258,289,319,350]
    months     = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','Dec2']
    for m, d in zip(months, month_doys):
        g, t, r = get_vege_state(vege, d)
        print(f"{m:<8} {d:>5}   {g*100:>9.1f}%   {t*100:>9.1f}%   {r:>8.0f} mm")
