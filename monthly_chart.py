"""
PERFECT-Python — monthly water balance summary chart
Layout (matching reference image):
  Header       : title + climate/soil/crop/run info
  Upper panel  : rainfall bars + transpiration + soil evap + runoff lines
  Lower panel  : deep drainage + erosion (dashed) lines
  Annual labels: coloured totals strip (Rainfall Nnn mm  Transpn Nnn mm ...)
  Table        : monthly values (rows) x months (cols) + annual total column
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
from datetime import datetime

# ── colours (matching reference image) ──────────────────────────────────
CR  = '#7AB8E0'   # rain bars — light blue
CT  = '#2A6E1A'   # transpiration — dark green
CE  = '#CC2222'   # soil evaporation — red
CO  = '#CC44CC'   # runoff — magenta/purple
CD  = '#1A3E8A'   # drainage — dark blue
CX  = '#888888'   # erosion — grey dashed
BG  = '#FFFFFF'
BGL = '#F5F8FC'   # chart background — very light blue-grey
FG  = '#1A1814'

MO  = ['Jan','Feb','Mar','Apr','May','Jun',
       'Jul','Aug','Sep','Oct','Nov','Dec']
X   = list(range(12))

FS      = 22    # base / axis tick labels
FS_SM   = 19    # secondary labels
FS_TBL  = 17    # table body
FS_HDR  = 18    # table column headers
FS_TITL = 26    # main title
FS_SUB  = 17    # subtitle line
FS_ANN  = 20    # annual summary labels


def _rc():
    plt.rcParams.update({
        'font.family'      : 'sans-serif',
        'font.size'        : FS,
        'axes.facecolor'   : BGL,
        'figure.facecolor' : BG,
        'axes.linewidth'   : 1.0,
        'xtick.major.width': 1.0,
        'ytick.major.width': 1.0,
        'xtick.major.size' : 5,
        'ytick.major.size' : 5,
        'xtick.color'      : FG,
        'ytick.color'      : FG,
        'text.color'       : FG,
        'axes.labelcolor'  : FG,
    })


def _cell(ax, x, y, text, w, h, bg=BG, fg=FG,
          bold=False, align='right', fs=None):
    fs = fs or FS_TBL
    ax.add_patch(FancyBboxPatch((x, y), w, h,
        boxstyle='square,pad=0', facecolor=bg,
        edgecolor='#C8C4BC', linewidth=0.5, zorder=2))
    xp = x + w * (0.93 if align == 'right' else 0.05)
    ax.text(xp, y + h * 0.5, text,
            ha=align, va='center', fontsize=fs,
            fontfamily='monospace',
            fontweight='bold' if bold else 'normal',
            color=fg, zorder=3)


def make_monthly_chart(ann, mon, profile, nyears, err_mm_yr,
                       title_str, out_path,
                       climate_name='', soil_name='', crop_name=''):
    _rc()

    # ── means ──────────────────────────────────────────────────────────────
    rain_m = float(ann['rain'].mean())
    ro_m   = float(ann['runoff'].mean())
    dr_m   = float(ann['drainage'].mean())
    ev_m   = float(ann['soil_evap'].mean())
    tr_m   = float(ann['transp'].mean())
    sed_m  = float(ann['sediment'].mean()) if 'sediment' in ann.columns else 0.0

    m_rain = mon['rain'].tolist()
    m_ro   = mon['runoff'].tolist()
    m_ev   = mon['soil_evap'].tolist()
    m_tr   = mon['transp'].tolist()
    m_dr   = mon['drainage'].tolist()
    m_sed  = mon['sediment'].tolist() if 'sediment' in mon.columns else [0.0]*12

    run_dt = datetime.now().strftime('%d %b %Y  %H:%M')

    # ── figure
    fig = plt.figure(figsize=(20, 28))
    fig.patch.set_facecolor(BG)

    # Header drawn at figure level — reliable at any figure size
    from matplotlib.patches import FancyBboxPatch as _FBP
    fig.add_artist(_FBP(
        (0.03, 0.955), 0.94, 0.040,
        boxstyle='round,pad=0.008', facecolor='#EAE6DB',
        edgecolor='#C0BAA8', linewidth=1.2,
        transform=fig.transFigure, zorder=3, clip_on=False))
    fig.text(0.50, 0.976, title_str,
             ha='center', va='center',
             fontsize=FS_TITL, fontweight='bold', color=FG, zorder=4)
    parts = []
    if climate_name: parts.append(f'Climate: {climate_name}')
    if soil_name:    parts.append(f'Soil: {soil_name}')
    if crop_name:    parts.append(f'Crop: {crop_name}')
    parts.append(f'Run: {run_dt}')
    fig.text(0.50, 0.959, '   ·   '.join(parts),
             ha='center', va='center',
             fontsize=FS_SUB, color='#5A5550', zorder=4)

    # 4 content rows — no header subplot needed
    gs = gridspec.GridSpec(4, 1,
        height_ratios=[2.6, 0.9, 0.08, 0.32],
        hspace=0.0,
        left=0.07, right=0.97, top=0.945, bottom=0.02)

    # ══════════════════════════════════════════════════════════════════════
    # Upper chart — rainfall bars + transpiration + soil evap + runoff
    # ══════════════════════════════════════════════════════════════════════
    ax_top = fig.add_subplot(gs[0])
    ax_top.set_facecolor(BGL)
    for sp in ['top', 'right']:
        ax_top.spines[sp].set_visible(False)
    ax_top.spines['bottom'].set_linewidth(0.5)
    ax_top.spines['bottom'].set_color('#CCCCCC')

    ax_top.bar(X, m_rain, color=CR, alpha=0.65, width=0.7, zorder=1, label='Rainfall')
    ax_top.plot(X, m_tr,  color=CT, lw=3.5, marker='o', ms=10, zorder=3, label='Transpn')
    ax_top.plot(X, m_ev,  color=CE, lw=3.5, marker='o', ms=10, zorder=3, label='Soil Evap.')
    ax_top.plot(X, m_ro,  color=CO, lw=3.5, marker='o', ms=10, zorder=3, label='Runoff')

    ax_top.legend(loc='upper right', fontsize=FS_SM,
                  frameon=True, framealpha=0.85,
                  edgecolor='#CCCCCC',
                  handlelength=2.0, handleheight=1.0,
                  markerscale=1.0)
    ax_top.axhline(0, color='#BBBBBB', lw=0.8)
    ax_top.set_xticks(X)
    ax_top.set_xticklabels([])
    ax_top.tick_params(axis='x', length=0)
    ax_top.set_ylabel('mm / month', fontsize=FS_SM, fontweight='bold')
    ax_top.yaxis.set_major_locator(ticker.MaxNLocator(nbins=5, integer=True))
    ax_top.tick_params(axis='y', labelsize=FS)
    ax_top.grid(axis='y', color='#E0E4EC', lw=0.7, zorder=0)

    # ══════════════════════════════════════════════════════════════════════
    # Lower chart — deep drainage + erosion
    # ══════════════════════════════════════════════════════════════════════
    ax_bot = fig.add_subplot(gs[1])
    ax_bot.set_facecolor(BGL)
    for sp in ['top', 'right']:
        ax_bot.spines[sp].set_visible(False)
    ax_bot.spines['top'].set_linewidth(0.5)
    ax_bot.spines['top'].set_color('#CCCCCC')

    ax_bot.plot(X, m_dr,  color=CD, lw=3.5, marker='o', ms=10, zorder=3, label='Drainage')
    ax_bot.plot(X, m_sed, color=CX, lw=2.5, marker='D', ms=8,  ls='--',  zorder=3, label='Erosion')

    ax_bot.legend(loc='upper right', fontsize=FS_SM,
                  frameon=True, framealpha=0.85,
                  edgecolor='#CCCCCC',
                  handlelength=2.5, handleheight=1.0)
    ax_bot.axhline(0, color='#BBBBBB', lw=0.8)
    ax_bot.set_xticks(X)
    ax_bot.set_xticklabels([])      # labels go in the annual strip below
    ax_bot.tick_params(axis='x', length=0)
    ax_bot.set_ylabel('mm or t/ha', fontsize=FS_SM, fontweight='bold')
    ax_bot.yaxis.set_major_locator(ticker.MaxNLocator(nbins=3, integer=False))
    ax_bot.tick_params(axis='y', labelsize=FS)
    ax_bot.grid(axis='y', color='#E0E4EC', lw=0.7, zorder=0)

    # Gap spacer
    ax_gap = fig.add_subplot(gs[2])
    ax_gap.axis('off')

    # ══════════════════════════════════════════════════════════════════════
    # Annual summary labels strip
    # ══════════════════════════════════════════════════════════════════════
    ax_ann = fig.add_subplot(gs[3])
    ax_ann.axis('off')
    ax_ann.set_facecolor(BG)
    ax_ann.set_xlim(0, 1); ax_ann.set_ylim(0, 1)

    items = [
        (f'Rainfall\n{rain_m:.0f}mm',   CR,  0.09),
        (f'Transpn\n{tr_m:.0f}mm',       CT,  0.26),
        (f'Soil Evap.\n{ev_m:.0f}mm',    CE,  0.43),
        (f'Runoff\n{ro_m:.0f}mm',        CO,  0.60),
        (f'Drainage\n{dr_m:.0f}mm',      CD,  0.77),
        (f'Erosion\n{sed_m:.1f}t/ha',    CX,  0.93),
    ]
    # Month labels sit at bottom of this strip, lined up with the chart columns
    # Map X positions 0-11 to axes fraction
    for j, m in enumerate(MO):
        xf = (j + 0.5) / 12.0
        ax_ann.text(xf, 0.62, m,
                    ha='center', va='center',
                    fontsize=FS, fontweight='bold', color=FG,
                    transform=ax_ann.transAxes)

    # Annual totals below the month labels
    for label, color, xpos in items:
        ax_ann.text(xpos, 0.15, label,
                    ha='center', va='center',
                    fontsize=FS_ANN, fontweight='bold',
                    color=color, transform=ax_ann.transAxes)


    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close()
    print(f'  Saved: {Path(out_path).name}')


# ── standalone test ────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from read_p51       import read_p51
    from soil_xml       import read_soil_xml
    from vege           import read_vege
    from run_simulation import (_run_daily, _monthly_means,
                                _annual_stats, _make_vege_fn)

    lat, met  = read_p51('/mnt/user-data/uploads/Greenwood.p51')
    profile   = read_soil_xml('/mnt/user-data/uploads/Black_earth_4_layer.soil')
    vege_obj  = read_vege('/mnt/user-data/uploads/wheat_stubble_incorporated.vege')
    get_state = _make_vege_fn(vege_obj)

    df, sw0, swf = _run_daily(met, profile, get_state)
    nyears  = met.index.year.nunique()
    dsw     = swf - sw0
    ann     = _annual_stats(df)
    mon     = _monthly_means(df, nyears)
    err     = (df.rain.sum() - df.runoff.sum() - df.drainage.sum()
               - df.soil_evap.sum() - df.transp.sum() - dsw) / nyears

    make_monthly_chart(
        ann, mon, profile, nyears, err,
        title_str    = 'Water balance summary  Greenwood  1977–1984',
        out_path     = '/mnt/user-data/outputs/monthly_summary_chart.png',
        climate_name = 'Oakey Aero (SILO P51)',
        soil_name    = profile.name,
        crop_name    = vege_obj.name,
    )
