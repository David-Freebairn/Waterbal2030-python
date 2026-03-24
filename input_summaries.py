"""
PERFECT-Python — Soil and Vegetation input summary graphics
Matches the HowLeaky panel style shown in reference images.
"""

import warnings
warnings.filterwarnings('ignore')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as ticker
from matplotlib.patches import FancyBboxPatch, Rectangle
from pathlib import Path
from datetime import datetime, date, timedelta

BG  = '#FAFAF8'
BG2 = '#F0EDE4'
BG3 = '#E4E0D5'
FG  = '#1A1814'
FG2 = '#5A5550'
FG3 = '#9E9B95'

FS_SM   = 9.5
FS_TBL  = 10
FS_HDR  = 11
FS_TITL = 20
FS_SUB  = 11


def _rc():
    plt.rcParams.update({
        'font.family'     : 'sans-serif',
        'font.size'       : 10,
        'axes.facecolor'  : BG,
        'figure.facecolor': BG,
    })


def _doy_to_date_str(doy):
    d = date(2001, 1, 1) + timedelta(days=int(doy) - 1)
    return f'{d.day:02d} {d.strftime("%b")}'


# ══════════════════════════════════════════════════════════════════════════
# SOIL SUMMARY
# ══════════════════════════════════════════════════════════════════════════

def make_soil_summary(profile, out_path, created='', modified=''):
    _rc()
    n   = len(profile.layers)
    run_dt = datetime.now().strftime('%d %b %Y  %H:%M')

    # ksat in model is mm/hr; PERFECT original is mm/day
    ksat_day = [l.ksat * 24 for l in profile.layers]

    # Row definitions: (number_str, label, colour_group, values_list, units_str)
    # colour_group: 'blue'=soil moisture, 'purple'=evap, 'green'=erosion, ''=>plain
    ROWS = [
        ('1.',  'Number of Horizons',          '',       [str(n)],
                                                          ''),
        ('2.',  'Layer Depth (Cumulative)',     '',
                [f'{l.depth_mm:.0f}' for l in profile.layers],
                'mm'),
        ('3.',  'Air dry moisture (AD)',        'blue',
                [f'{l.airdry*100:.0f}' for l in profile.layers],
                '%Vol'),
        ('4.',  'Wilting point (WP)',           'blue',
                [f'{l.ll*100:.0f}' for l in profile.layers],
                '%Vol'),
        ('5.',  'Field capacity (FC)',          'blue',
                [f'{l.dul*100:.0f}' for l in profile.layers],
                '%Vol'),
        ('6.',  'Sat. water content (Sat)',     'blue',
                [f'{l.sat*100:.0f}' for l in profile.layers],
                '%Vol'),
        ('7.',  'Max. drainage from layer',     '',
                [f'{v:.0f}' for v in ksat_day],
                'mm/day'),
        ('8.',  'Bulk density',                 '',
                [f'{l.bulk_density:.2f}' for l in profile.layers],
                'g/cm³'),
        ('9.',  'PAWC per layer',               'blue',
                [f'{l.pawc:.0f}' for l in profile.layers],
                f'mm  (total = {profile.pawc_total:.0f} mm)'),
        ('',    '',                             '',       [],  ''),  # spacer
        ('10.', 'Stage 1 evap. (U)',            'purple',
                [f'{profile.u:.0f}'],  'mm'),
        ('11.', 'Stage 2 evap. (Cona)',         'purple',
                [f'{profile.cona:.0f}'],  'mm/day^0.5'),
        ('12.', 'Runoff Curve Number (CN)',     '',
                [f'{profile.cn2_bare:.0f}'],  'CN units (bare soil)'),
        ('13.', 'CN reduction cover',           '',
                [f'{profile.cn_cover_reduction:.0f}'],  'CN units at 100% cover'),
        ('14.', 'Erodibility (K)',              'green',
                [f'{profile.musle_k:.2f}'],  'metric'),
        ('15.', 'Field Slope (S)',              'green',
                [f'{profile.slope_pct:.0f}'],  '%'),
        ('16.', 'Slope Length (L)',             'green',
                [f'{profile.slope_length:.0f}'],  'm'),
        ('17.', 'Practice factor (P)',          'green',
                [f'{profile.musle_p:.1f}'],  '(0-1)'),
        ('18.', 'CN Reduction – Tillage',       '',
                [f'{profile.cn_tillage_max:.0f}'],  ''),
        ('19.', 'Rainfall to 0 roughness',      '',
                [f'{profile.cn_roughness_rain:.0f}'],  'mm'),
        ('20.', 'Sediment Delivery Ratio',      '',
                ['0.1'],  '(0-1)'),
        ('21.', 'Rill/interrill ratio',         '',
                [f'{profile.rill_ratio:.0f}'],  '(0-1)'),
    ]

    n_data_rows = sum(1 for r in ROWS if r[1])   # non-spacer rows
    n_total     = len(ROWS)   # includes spacers

    # Fixed column layout (normalised 0-1 x-space)
    # No left number column — parameter name starts at left edge
    NAME_X = 0.01   # parameter name start
    NAME_W = 0.30   # parameter name width
    VAL_X  = 0.32   # first value col start
    VAL_W  = 0.090  # each value col width
    UNIT_X = VAL_X + n * VAL_W + 0.01
    RH     = 0.033  # row height in axes units
    HDR_H  = 0.045  # section header height
    TITL_H = 0.08   # title area height

    total_rows_h = n_total * RH + HDR_H + TITL_H + 0.04
    fig_h = max(9, total_rows_h / 0.85 * 10)

    fig, ax = plt.subplots(figsize=(13, fig_h))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.axis('off')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    # ── Title — matches reference image header style ───────────────────────
    from matplotlib.patches import FancyBboxPatch as _FBP
    ax.add_patch(_FBP((0.0, 0.945), 1.0, 0.055,
        boxstyle='round,pad=0.005', facecolor='#EAE6DB',
        edgecolor='#C0BAA8', linewidth=1.2,
        transform=ax.transAxes, zorder=1, clip_on=False))
    ax.text(0.50, 0.978, profile.name,
            ha='center', va='center',
            fontsize=FS_TITL, fontweight='bold', color=FG,
            transform=ax.transAxes, zorder=2)
    ax.text(0.50, 0.958,
            f'Soil profile input summary     Run: {run_dt}',
            ha='center', va='center',
            fontsize=FS_SM, color='#5A5550',
            transform=ax.transAxes, zorder=2)

    # ── Section header ───────────────────────────────────────────────────
    sec_y = 0.87
    ax.add_patch(Rectangle((0.01, sec_y - 0.01), 0.98, HDR_H,
        facecolor=BG3, edgecolor='#C0BAA8', linewidth=0.6,
        transform=ax.transAxes, zorder=1))
    ax.text(0.02, sec_y + HDR_H * 0.45, 'Input parameters',
            fontsize=FS_HDR, fontweight='bold', color=FG,
            va='center', transform=ax.transAxes)

    # ── Column headers (layer depths) ────────────────────────────────────
    hdr_y = sec_y - 0.022
    ax.text(NAME_X, hdr_y, 'Parameter',
            fontsize=FS_HDR, fontweight='bold', color=FG,
            va='center', transform=ax.transAxes)
    for i, lyr in enumerate(profile.layers):
        xc = VAL_X + i * VAL_W + VAL_W * 0.5
        ax.text(xc, hdr_y, f'{lyr.depth_mm:.0f}',
                fontsize=FS_SM, color=FG2, va='center', ha='center',
                transform=ax.transAxes)
    ax.text(UNIT_X, hdr_y, 'Units / notes',
            fontsize=FS_SM, color=FG2, va='center',
            transform=ax.transAxes)

    # ── Data rows ────────────────────────────────────────────────────────
    COLOUR = {
        'blue'  : ('#3A78A8', '#EAF2F8'),
        'purple': ('#8050A8', '#F3EDF8'),
        'green' : ('#3A8050', '#EAF5EE'),
        ''      : (FG,        BG),
    }

    y = hdr_y - RH * 0.3
    for num, label, grp, vals, units in ROWS:
        if not label:
            y -= RH * 0.5
            continue

        fg_c, bg_c = COLOUR[grp]

        # row background
        ax.add_patch(Rectangle((0.01, y - RH * 0.85), 0.98, RH,
            facecolor=bg_c, edgecolor='#D4CFBF', linewidth=0.4,
            transform=ax.transAxes, zorder=1))

        # label
        ax.text(NAME_X, y - RH * 0.35, label,
                fontsize=FS_TBL, color=fg_c, fontweight='normal',
                va='center', transform=ax.transAxes)

        # values in boxes
        for i, v in enumerate(vals[:n]):
            xc = VAL_X + i * VAL_W
            ax.add_patch(FancyBboxPatch(
                (xc + 0.003, y - RH * 0.82), VAL_W - 0.008, RH * 0.72,
                boxstyle='round,pad=0.005',
                facecolor='white', edgecolor='#B8B3A5', linewidth=0.6,
                transform=ax.transAxes, zorder=2))
            ax.text(xc + VAL_W * 0.5, y - RH * 0.35, v,
                    fontsize=FS_TBL, color=FG,
                    ha='center', va='center',
                    transform=ax.transAxes, zorder=3)

        # units
        if units:
            ax.text(UNIT_X, y - RH * 0.35, units,
                    fontsize=FS_SM, color=FG2,
                    va='center', transform=ax.transAxes)

        y -= RH

    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close()
    print(f'  Saved: {Path(out_path).name}')


# ══════════════════════════════════════════════════════════════════════════
# VEGETATION SUMMARY
# ══════════════════════════════════════════════════════════════════════════

def make_vege_summary(vege, out_path, created='', modified=''):
    _rc()
    run_dt = datetime.now().strftime('%d %b %Y  %H:%M')

    # ── extract schedule ──────────────────────────────────────────────────
    if hasattr(vege, 'doy') and hasattr(vege, 'residue_cover'):
        # CoverSchedule from cover_excel.py
        doys   = list(vege.doy)
        greens = [v * 100 for v in vege.green_cover]
        resids = [v * 100 for v in vege.residue_cover]
        roots  = list(vege.root_depth)
        name   = vege.name
        wue    = float(vege.tue) if getattr(vege, 'tue', 0.0) > 0 else None
        hi     = float(vege.hi)  if getattr(vege, 'hi',  0.0) > 0 else None
    else:
        # VegeTemplate from vege.py
        doys   = [int(d) for d in vege.doy]
        greens = [float(g) * 100 for g in vege.green_cover]
        totals_sched = [float(t) * 100 for t in vege.total_cover]
        resids = [max(0.0, t - g) for t, g in zip(totals_sched, greens)]
        # Fractional cover model for display
        roots  = [float(r) for r in vege.root_depth]
        name   = vege.name if isinstance(vege.name, str) else ''.join(vege.name)
        wue    = float(vege.water_use_effic)   # TUE (g/m2/mm transpiration)
        hi     = float(vege.harvest_index)      # fraction

    # Compute total cover via fractional cover model for display
    totals = [g + (100 - g) / 100 * r for g, r in zip(greens, resids)]
    n_pts = len(doys)

    # interpolated daily series for chart
    doy_d   = list(range(1, 366))
    g_d     = np.interp(doy_d, doys, greens)
    r_d     = np.interp(doy_d, doys, resids)
    root_d  = np.interp(doy_d, doys, roots)
    total_d = g_d + r_d

    # ── figure: 2 rows — chart (top) + table (bottom) ────────────────────
    fig = plt.figure(figsize=(12, 12))
    fig.patch.set_facecolor(BG)

    gs = gridspec.GridSpec(2, 1,
        height_ratios=[1.4, 3.2],
        hspace=0.30,
        left=0.04, right=0.97, top=0.93, bottom=0.02)

    # ── Title — matches reference image header style ───────────────────────
    from matplotlib.patches import FancyBboxPatch as _FBP
    _hbox = _FBP((0.0, 0.958), 1.0, 0.042,
        boxstyle='round,pad=0.005', facecolor='#EAE6DB',
        edgecolor='#C0BAA8', linewidth=1.2,
        transform=fig.transFigure, zorder=1, clip_on=False)
    fig.add_artist(_hbox)
    fig.text(0.50, 0.979, name,
             ha='center', va='center',
             fontsize=FS_TITL, fontweight='bold', color=FG, zorder=2)
    fig.text(0.50, 0.962,
             f'Vegetation input summary     Run: {run_dt}',
             ha='center', va='center',
             fontsize=FS_SM, color='#5A5550', zorder=2)

    # TUE / HI parameter line (only for VegeTemplate)
    if wue is not None and hi is not None:
        param_line = (f'TUE = {wue:.1f} g/m²/mm transpiration     '
                      f'Harvest Index = {hi:.2f}     '
                      f'→ Mean yield ≈ transpiration × {wue:.1f} × {hi:.2f} / 1000  t/ha')
        fig.text(0.04, 0.935, param_line,
                 fontsize=FS_SM, color='#2C5F8A', va='top', fontweight='bold')
        # Shrink top margin slightly to fit param line
        gs.update(top=0.88)

    # ── Cover chart ───────────────────────────────────────────────────────
    ax_cov = fig.add_subplot(gs[0])
    ax_cov.set_facecolor('white')
    for spine in ax_cov.spines.values():
        spine.set_linewidth(0.6)
        spine.set_color('#C0BAA8')

    # stacked fill: amber (residue) underneath, green on top
    ax_cov.fill_between(doy_d, 0, total_d,
                        color='#C8A050', alpha=0.40, zorder=1)
    ax_cov.fill_between(doy_d, 0, g_d,
                        color='#60A850', alpha=0.55, zorder=2)

    # root depth on secondary axis (below the cover chart, brown fill)
    ax_r = ax_cov.twinx()
    ax_r.fill_between(doy_d, 0, root_d,
                      color='#7A5030', alpha=0.28, zorder=0)
    ax_r.set_ylim(max(root_d) * 3.5 if max(root_d) > 0 else 1, 0)  # inverted, roots down
    ax_r.set_ylabel('Root depth (mm)', fontsize=FS_SM, color='#7A5030')
    ax_r.tick_params(axis='y', labelsize=FS_SM, labelcolor='#7A5030')
    ax_r.yaxis.set_major_locator(ticker.MaxNLocator(nbins=3, integer=True))
    ax_r.spines['right'].set_linewidth(0.6)
    ax_r.spines['right'].set_color('#C0BAA8')
    ax_r.spines['top'].set_visible(False)

    ax_cov.set_xlim(1, 365)
    ax_cov.set_ylim(0, 108)
    ax_cov.set_yticks([0, 25, 50, 75, 100])
    ax_cov.set_yticklabels(['0', '25', '50', '75', '100'], fontsize=FS_SM)
    ax_cov.set_ylabel('Cover (%)', fontsize=FS_SM)

    month_starts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 365]
    month_names  = ['Jan','Feb','Mar','Apr','May','Jun',
                    'Jul','Aug','Sep','Oct','Nov','Dec','']
    ax_cov.set_xticks(month_starts)
    ax_cov.set_xticklabels(month_names, fontsize=FS_SM)
    ax_cov.tick_params(axis='x', length=0)

    # horizontal midline
    ax_cov.axhline(50, color='#C0BAA8', lw=0.5, ls='-', zorder=0)

    # ── Data table ────────────────────────────────────────────────────────
    ax_tbl = fig.add_subplot(gs[1])
    ax_tbl.axis('off')
    ax_tbl.set_xlim(0, 1)
    ax_tbl.set_ylim(0, 1)

    # Column positions and widths
    cols = [
        ('#',          0.01, 0.060),
        ('Date',       0.07, 0.110),
        ('JDay',       0.18, 0.085),
        ('Green %',    0.27, 0.110),
        ('Residue %',  0.38, 0.110),
        ('Total %',    0.49, 0.110),
        ('Roots mm',   0.60, 0.110),
    ]

    RH2 = min(0.82 / (n_pts + 1.5), 0.065)
    hdr_y = 0.97

    # header row
    for hdr, cx, cw in cols:
        ax_tbl.add_patch(Rectangle((cx, hdr_y - RH2), cw - 0.005, RH2,
            facecolor=BG3, edgecolor='#C0BAA8', linewidth=0.5, zorder=1))
        ax_tbl.text(cx + cw * 0.5, hdr_y - RH2 * 0.5, hdr,
                    fontsize=FS_HDR, fontweight='bold', color=FG,
                    ha='center', va='center', zorder=2)

    # data rows
    for i, (doy, g, r, tot_cov, root) in enumerate(zip(doys, greens, resids, totals, roots)):
        shade = '#EDEBE2' if i % 2 == 0 else BG
        ry = hdr_y - (i + 2) * RH2

        tot = g + (100 - g) / 100 * r
        row_vals = [
            (f'({i+1})', 'center'),
            (_doy_to_date_str(doy), 'left'),
            (f'{int(doy)}', 'center'),
            (f'{g:.0f}', 'center'),
            (f'{r:.1f}', 'center'),
            (f'{tot:.1f}', 'center'),
            (f'{root:.0f}', 'center'),
        ]

        for j, ((txt, ha), (_, cx, cw)) in enumerate(zip(row_vals, cols)):
            ax_tbl.add_patch(Rectangle((cx, ry), cw - 0.005, RH2,
                facecolor=shade, edgecolor='#D4CFBF',
                linewidth=0.4, zorder=1))
            xp = cx + (cw * 0.05 if ha == 'left' else cw * 0.5)
            ax_tbl.text(xp, ry + RH2 * 0.5, txt,
                        fontsize=FS_TBL, color=FG,
                        ha=ha, va='center', zorder=2)

    # ── TUE / HI parameter rows below the schedule table ────────────────
    if wue is not None and hi is not None:
        param_rows = [
            ('Transpiration use efficiency (TUE)', f'{wue:.1f}', 'g/m² per mm transpiration'),
            ('Harvest index (HI)',          f'{hi:.2f}', '(0-1)  →  Yield = Transpiration × TUE × HI / 1000  (t/ha)'),
        ]
        pr_rh = RH2 * 1.1
        pr_y  = hdr_y - (n_pts + 1.5) * RH2 - pr_rh * 0.5
        for pi, (plabel, pval, punits) in enumerate(param_rows):
            bg_p = '#EAF2F8' if pi % 2 == 0 else '#D6EAF8'
            # label cell (spans first 4 cols)
            ax_tbl.add_patch(Rectangle((0.01, pr_y), 0.45, pr_rh,
                facecolor=bg_p, edgecolor='#C0BAA8', linewidth=0.5, zorder=1))
            ax_tbl.text(0.025, pr_y + pr_rh * 0.5, plabel,
                        fontsize=FS_TBL, fontweight='bold', color='#2C5F8A',
                        va='center', zorder=2)
            # value cell
            ax_tbl.add_patch(Rectangle((0.47, pr_y), 0.12, pr_rh,
                facecolor=bg_p, edgecolor='#C0BAA8', linewidth=0.5, zorder=1))
            ax_tbl.text(0.53, pr_y + pr_rh * 0.5, pval,
                        fontsize=FS_TBL, fontweight='bold', color=FG,
                        ha='center', va='center', zorder=2)
            # units cell
            ax_tbl.add_patch(Rectangle((0.60, pr_y), 0.39, pr_rh,
                facecolor=bg_p, edgecolor='#C0BAA8', linewidth=0.5, zorder=1))
            ax_tbl.text(0.61, pr_y + pr_rh * 0.5, punits,
                        fontsize=FS_TBL - 1, color=FG2,
                        va='center', zorder=2)
            pr_y -= pr_rh

    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close()
    print(f'  Saved: {Path(out_path).name}')


# ── wire into launch.py via this function ─────────────────────────────────
def make_input_summaries(profile, vege, out_dir):
    """Generate both soil and vege summary PNGs into out_dir."""
    out_dir = Path(out_dir)
    soil_path = out_dir / f'{profile.name.replace(" ","_")}_soil_summary.png'
    vege_name = vege.name if isinstance(vege.name, str) else ''.join(vege.name)
    vege_path = out_dir / f'{vege_name.replace(" ","_")}_vege_summary.png'
    make_soil_summary(profile, soil_path)
    make_vege_summary(vege, vege_path)
    return soil_path, vege_path


# ── standalone test ────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from soil_xml import read_soil_xml
    from vege     import read_vege

    profile  = read_soil_xml('/mnt/user-data/uploads/Black_earth_4_layer.soil')
    vege_obj = read_vege('/mnt/user-data/uploads/wheat_stubble_incorporated.vege')

    make_soil_summary(profile,
        out_path='/mnt/user-data/outputs/soil_summary.png')
    make_vege_summary(vege_obj,
        out_path='/mnt/user-data/outputs/vege_summary.png')
