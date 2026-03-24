"""
PERFECT-Python — standard output chart
Layout:
  Header   Site / soil / crop / run date block  (full width)
  S1a      Monthly WB table                     (full width)
  S1b      Monthly WB + erosion chart            (full width)
  S2       Annual summary table  |  Pie          (full width)
  S3       Annual time series: runoff | drainage | erosion
"""

import warnings
warnings.filterwarnings('ignore')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as ticker
from matplotlib.patches import FancyBboxPatch
from pathlib import Path
from datetime import datetime

# ── palette ─────────────────────────────────────────────────────────────
CR = '#5A96D4'; CO = '#2C4A7A'; CE = '#C8402A'
CT = '#4A8A3A'; CD = '#C48A18'; CS = '#888780'; CX = '#8B3A8B'
BG = '#FAFAF8'; BG2 = '#F2EFE8'
MO = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
X  = list(range(12))

FS       = 18    # base
FS_SM    = 15    # small labels / tick labels
FS_TBL   = 15    # table body
FS_HDR   = 16    # table column headers
FS_TITLE = 17    # panel titles
FS_SUPER = 24    # header main title
FGALL    = '#1A1814'   # all text black


def _rc():
    plt.rcParams.update({
        'font.family'      : 'sans-serif',
        'font.size'        : FS,
        'axes.spines.top'  : False,
        'axes.spines.right': False,
        'axes.linewidth'   : 0.6,
        'xtick.major.width': 0.5,
        'ytick.major.width': 0.5,
        'axes.facecolor'   : BG,
        'figure.facecolor' : BG,
        'xtick.labelsize'  : FS_SM,
        'ytick.labelsize'  : FS_SM,
        'xtick.color'      : '#1A1814',
        'ytick.color'      : '#1A1814',
        'axes.labelcolor'  : '#1A1814',
        'text.color'       : '#1A1814',
        'legend.fontsize'  : FS_SM,
        'axes.titlesize'   : FS_TITLE,
        'xtick.major.size' : 5,
        'ytick.major.size' : 5,
        'axes.linewidth'   : 1.0,
        'xtick.major.width': 1.0,
        'ytick.major.width': 1.0,
    })


def _cell(ax, x, y, text, w, h, bg=BG, fg='#1A1814',
          bold=False, align='right', fs=FS_TBL):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
        boxstyle='square,pad=0', facecolor=bg,
        edgecolor='#D0CCB8', linewidth=0.4, zorder=2))
    xp = x + w * (0.93 if align == 'right' else 0.05)
    ax.text(xp, y + h * 0.5, text,
            ha=align, va='center', fontsize=fs,
            fontfamily='monospace',
            fontweight='bold' if bold else 'normal',
            color=fg, zorder=3)


def _mon_set_x(ax):
    ax.set_xticks(X)
    ax.set_xticklabels(MO, fontsize=FS_SM)


def make_output_chart(ann, mon, profile, nyears, dsw_total, err_mm_yr,
                      title_str, out_path,
                      climate_name='', soil_name='', crop_name=''):
    _rc()

    rain_m = float(ann['rain'].mean())
    ro_m   = float(ann['runoff'].mean())
    dr_m   = float(ann['drainage'].mean())
    ev_m   = float(ann['soil_evap'].mean())
    tr_m   = float(ann['transp'].mean())
    et_m   = float(ann['et'].mean())
    sed_m  = float(ann['sediment'].mean()) if 'sediment' in ann.columns else 0.0

    def pct(v): return f'{v/rain_m*100:.1f}%'
    def cv(s):  return f'{s.std()/max(s.mean(),0.1)*100:.0f}%'

    m_rain = mon['rain'].tolist()
    m_ro   = mon['runoff'].tolist()
    m_ev   = mon['soil_evap'].tolist()
    m_tr   = mon['transp'].tolist()
    m_dr   = mon['drainage'].tolist()
    m_dsw  = mon['dsw'].tolist()
    m_sed  = mon['sediment'].tolist() if 'sediment' in mon.columns else [0]*12
    ann_idx     = ann.index.tolist()
    year_labels = [str(y) for y in ann_idx]

    # ── Cap annual time-series panels at 8 years ──────────────────────────
    # Long runs make the bar charts unreadable and can cause savefig to fail.
    # Monthly means and the summary table always use the full record.
    MAX_TS_YEARS = 8
    _ts_truncated = len(ann_idx) > MAX_TS_YEARS
    ann_ts        = ann.iloc[:MAX_TS_YEARS]          # first 8 years only
    ann_ts_idx    = ann_idx[:MAX_TS_YEARS]
    year_labels_ts = year_labels[:MAX_TS_YEARS]

    # ── figure ────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(22, 36))
    fig.patch.set_facecolor(BG)

    # 5 rows: header | tbl | chart | annual-summary | ts
    gs = gridspec.GridSpec(5, 1,
        height_ratios=[0.18, 1.8, 1.8, 2.0, 2.4],
        hspace=0.48,
        left=0.04, right=0.97, top=0.97, bottom=0.03)

    # ══════════════════════════════════════════════════════════════════════
    # Header
    # ══════════════════════════════════════════════════════════════════════
    ax_hdr = fig.add_subplot(gs[0])
    ax_hdr.axis('off')
    ax_hdr.set_xlim(0, 1); ax_hdr.set_ylim(0, 1)
    ax_hdr.add_patch(FancyBboxPatch((0.0, 0.0), 1.0, 1.0,
        boxstyle='round,pad=0.02', facecolor='#EAE6DB',
        edgecolor='#C0BAA8', linewidth=1.2, zorder=1,
        transform=ax_hdr.transAxes, clip_on=False))

    run_dt = datetime.now().strftime('%d %b %Y  %H:%M')
    ax_hdr.text(0.5, 0.64, title_str,
        ha='center', va='center',
        fontsize=FS_SUPER, fontweight='bold', color='#1A1814',
        transform=ax_hdr.transAxes, zorder=2)

    parts = []
    if climate_name: parts.append(f'Climate: {climate_name}')
    if soil_name:    parts.append(f'Soil: {soil_name}')
    if crop_name:    parts.append(f'Crop / Vegetation: {crop_name}')
    parts.append(f'Run: {run_dt}')
    ax_hdr.text(0.5, 0.18, '     ·     '.join(parts),
        ha='center', va='center',
        fontsize=FS_SM, color='#5A5550',
        transform=ax_hdr.transAxes, zorder=2)

    # ══════════════════════════════════════════════════════════════════════
    # S1a — monthly table (full width)
    # ══════════════════════════════════════════════════════════════════════
    ax_tbl = fig.add_subplot(gs[1])

    # Column widths: label col wider, 12 month cols + total
    # We map these into axes units [0, 1] via a normalised coordinate system
    # Total "units": label=3.2, each month=1.0, total=1.2  => 3.2+12+1.2 = 16.4
    TW   = 16.4   # total width units
    LW   = 2.4    # label col (narrowed)
    CW   = 1.05   # month col
    TOT  = 1.35   # total col
    rh   = 0.115  # row height as fraction of axes y (7 data + 1 header = 8 rows)
    hh   = 0.10
    nrows = 7

    # y coords: rows stack upward; use axes fraction [0,1]
    # total height needed = nrows*rh + hh + small margin
    # we normalise the ax to show exactly this
    ax_tbl.set_xlim(0, TW)
    total_h = nrows * rh + hh + 0.02
    ax_tbl.set_ylim(0, total_h)
    ax_tbl.axis('off')
    ax_tbl.set_title('Monthly water balance  (mm/month — long-term means)',
                     fontweight='normal', fontsize=FS_TITLE, pad=8, loc='left')

    row_data = [
        ('Rainfall',       m_rain, CR,         '#1A1814'),
        ('Runoff',         m_ro,   '#E8EEF8',  CO),
        ('Evaporation',    m_ev,   '#FBF0EC',  CE),
        ('Transpiration',  m_tr,   '#ECF4ED',  CT),
        ('Deep drainage',  m_dr,   '#FDF7EA',  CD),
        ('ΔSoil water',    m_dsw,  BG2,        CS),
        ('Erosion (t/ha)', m_sed,  '#F5EBF5',  CX),
    ]

    # header row
    hy = nrows * rh + 0.01
    _cell(ax_tbl, 0,  hy, 'Component', w=LW, h=hh,
          bg=BG2, bold=True, align='left', fs=FS_HDR)
    for j, m in enumerate(MO):
        _cell(ax_tbl, LW + j*CW, hy, m, w=CW, h=hh,
              bg=BG2, bold=True, align='right', fs=FS_HDR)
    _cell(ax_tbl, LW + 12*CW, hy, 'Total', w=TOT, h=hh,
          bg=BG2, bold=True, align='right', fs=FS_HDR)

    for i, (lab, vals, bg, fg) in enumerate(row_data):
        ry = (nrows - 1 - i) * rh
        _cell(ax_tbl, 0, ry, lab, w=LW, h=rh,
              bg=bg, fg=fg, bold=(i == 0), align='left', fs=FS_TBL)
        tot = sum(vals)
        for j, v in enumerate(vals):
            txt = f'{v:.2f}' if 'Erosion' in lab else \
                  (f'{v:.0f}' if abs(v) >= 1 else f'{v:.1f}')
            _cell(ax_tbl, LW + j*CW, ry, txt, w=CW, h=rh,
                  bg=bg, fg=fg, fs=FS_TBL)
        tot_txt = f'{tot:.2f}' if 'Erosion' in lab else \
                  (f'{tot:.0f}' if abs(tot) >= 1 else f'{tot:.1f}')
        _cell(ax_tbl, LW + 12*CW, ry, tot_txt, w=TOT, h=rh,
              bg=BG2, fg=fg, bold=True, fs=FS_TBL)

    # ══════════════════════════════════════════════════════════════════════
    # S1b — monthly chart (full width)
    # ══════════════════════════════════════════════════════════════════════
    ax_ch = fig.add_subplot(gs[2])

    # secondary y for erosion — dashed black line, no fill
    ax_chb = ax_ch.twinx()
    ax_chb.plot(X, m_sed, color='#1A1814', lw=2.0, ls='--',
                marker='D', ms=5, zorder=4, label='Erosion (t/ha)')
    ax_chb.set_ylabel('Erosion (t/ha / month)', fontsize=FS_SM, color='#1A1814')
    ax_chb.tick_params(axis='y', labelsize=FS_SM, labelcolor='#1A1814')
    ax_chb.yaxis.set_major_locator(ticker.MaxNLocator(nbins=4))
    ax_chb.spines['right'].set_visible(True)
    ax_chb.spines['right'].set_linewidth(0.8)
    ax_chb.spines['right'].set_color('#1A1814')
    ax_chb.spines['top'].set_visible(False)

    ax_ch.bar(X, m_rain, color=CR, alpha=0.40, width=0.7, zorder=1, label='Rainfall')
    ax_ch.plot(X, m_ro,  color=CO, lw=2.0, marker='o', ms=5,   zorder=3, label='Runoff')
    ax_ch.plot(X, m_ev,  color=CE, lw=2.0, marker='o', ms=5,   zorder=3, label='Evaporation')
    ax_ch.plot(X, m_tr,  color=CT, lw=2.0, marker='o', ms=5,   zorder=3, label='Transpiration')
    ax_ch.plot(X, m_dr,  color=CD, lw=1.7, marker='s', ms=4.5, zorder=3, label='Drainage')

    _mon_set_x(ax_ch)
    ax_ch.set_ylabel('mm / month', fontsize=FS_SM, color=FGALL)
    ax_ch.set_title('Monthly water balance & erosion chart',
                    fontweight='normal', fontsize=FS_TITLE, pad=8, loc='left')
    ax_ch.yaxis.set_major_locator(ticker.MaxNLocator(nbins=6, integer=True))

    h1, l1 = ax_ch.get_legend_handles_labels()
    h2, l2 = ax_chb.get_legend_handles_labels()
    ax_ch.legend(h1+h2, l1+l2, fontsize=FS_SM, frameon=False,
                 ncol=3, loc='upper left', borderpad=0.3)
    ax_ch.set_zorder(ax_chb.get_zorder()+1)
    ax_ch.patch.set_visible(False)

    # ══════════════════════════════════════════════════════════════════════
    # S2 — annual summary table  |  pie  (full width, side by side)
    # ══════════════════════════════════════════════════════════════════════
    gs2 = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[3],
          width_ratios=[1.2, 0.85], wspace=0.10)

    ax_t2 = fig.add_subplot(gs2[0])
    rh2=0.90; hh2=0.76; ncw=[2.6, 1.2, 0.85, 1.05]; nrows2=8
    ax_t2.set_xlim(0, sum(ncw))
    ax_t2.set_ylim(-0.05, nrows2*rh2 + hh2 + 0.12)
    ax_t2.axis('off')
    ax_t2.set_title('Annual water balance summary',
                    fontweight='normal', fontsize=FS_TITLE, pad=8, loc='left')

    ann_rows = [
        ('Rainfall',       rain_m,    cv(ann['rain']),        '100.0%', CR,         '#1A1814'),
        ('Runoff',         ro_m,      cv(ann['runoff']),       pct(ro_m), '#E8EEF8', CO),
        ('Evaporation',    ev_m,      cv(ann['soil_evap']),    pct(ev_m), '#FBF0EC', CE),
        ('Transpiration',  tr_m,      cv(ann['transp']),       pct(tr_m), '#ECF4ED', CT),
        ('Total ET',       et_m,      '—',                    pct(et_m), '#F0F5ED', CT),
        ('Deep drainage',  dr_m,      cv(ann['drainage']),     pct(dr_m), '#FDF7EA', CD),
        ('Erosion (t/ha)', sed_m,     cv(ann['sediment']),     '—',       '#F5EBF5', CX),
        ('Balance err mm', err_mm_yr, '—',                    '—',       BG2,       CS),
    ]

    x0 = 0
    hdr_y2 = nrows2*rh2 + 0.06
    for w, h in zip(ncw, ['Component', 'Mean / yr', 'CV', '% rain']):
        _cell(ax_t2, x0, hdr_y2, h, w=w, h=hh2, bg=BG2, bold=True,
              align='left' if x0==0 else 'right', fs=FS_HDR)
        x0 += w

    for i, (lab, val, cv_s, pct_s, bg, fg) in enumerate(ann_rows):
        ry = (nrows2-1-i) * rh2
        fmt = f'{val:.2f}' if 'Erosion' in lab else \
              f'{val:.3f}' if 'err' in lab else f'{val:.1f}'
        for k, (w, v) in enumerate(zip(ncw, [lab, fmt, cv_s, pct_s])):
            _cell(ax_t2, sum(ncw[:k]), ry, v, w=w, h=rh2, bg=bg, fg=fg,
                  bold=(i==0), align='left' if k==0 else 'right', fs=FS_TBL)

    ax_pie = fig.add_subplot(gs2[1])
    pie_v  = [ro_m, dr_m, ev_m, tr_m]
    pie_lb = [
        f'Runoff\n{ro_m:.0f} mm  {pct(ro_m)}',
        f'Drainage\n{dr_m:.0f} mm  {pct(dr_m)}',
        f'Soil evap\n{ev_m:.0f} mm  {pct(ev_m)}',
        f'Transpn\n{tr_m:.0f} mm  {pct(tr_m)}',
    ]
    ax_pie.pie(pie_v, labels=pie_lb, colors=[CO, CD, CE, CT],
               startangle=90, counterclock=False,
               wedgeprops=dict(linewidth=0.7, edgecolor='white'),
               textprops=dict(fontsize=FS_SM),
               labeldistance=1.22, radius=0.86)
    ax_pie.text(0, 0, f'Rain\n{rain_m:.0f}mm',
                ha='center', va='center',
                fontsize=FS, fontweight='bold', color='#1A1814')
    ax_pie.set_title('Annual water balance partitioning',
                     fontweight='normal', fontsize=FS_TITLE, pad=6, loc='center')

    # ══════════════════════════════════════════════════════════════════════
    # S3 — annual time series: runoff | drainage | erosion | yield
    #      Capped at first 8 years so the chart always renders cleanly.
    # ══════════════════════════════════════════════════════════════════════
    gs3 = gridspec.GridSpecFromSubplotSpec(1, 4, subplot_spec=gs[4], wspace=0.38)

    _ts_note = f'  (first {MAX_TS_YEARS} of {len(ann_idx)} yrs)' if _ts_truncated else ''

    def ts_panel(pos, title, color, series_vals, y_label, fmt_mean='.0f'):
        ax = fig.add_subplot(pos)
        ax2 = ax.twinx()
        ax2.bar(range(len(ann_ts_idx)), ann_ts['rain'].tolist(),
                color=CR, alpha=0.15, width=0.65, zorder=1)
        ax2.set_ylabel('Rainfall (mm)', fontsize=FS_SM, color=CS)
        ax2.tick_params(axis='y', labelsize=FS_SM, labelcolor=CS)
        ax2.yaxis.set_major_locator(ticker.MaxNLocator(nbins=4, integer=True))
        ax2.spines['right'].set_visible(True)
        ax2.spines['right'].set_linewidth(0.4)
        ax2.spines['right'].set_color(CS)
        ax2.spines['top'].set_visible(False)

        # series_vals is already sliced to MAX_TS_YEARS by caller
        mean_v = float(np.mean(series_vals))
        ax.bar(range(len(ann_ts_idx)), series_vals,
               color=color, alpha=0.78, width=0.65, zorder=3)
        ax.axhline(mean_v, color=color, lw=1.4, ls='--', zorder=4,
                   label=f'Mean  {mean_v:{fmt_mean}}')
        ax.set_title(title + _ts_note, fontweight='normal', fontsize=FS_TITLE)
        ax.set_ylabel(y_label, fontsize=FS_SM)
        ax.legend(fontsize=FS_SM, frameon=False, loc='upper left')
        ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=5, integer=True))
        ax.set_xlim(-0.6, len(ann_ts_idx) - 0.4)
        ax.set_ylim(bottom=0)
        ax.set_xticks(range(len(ann_ts_idx)))
        ax.set_xticklabels(year_labels_ts, fontsize=FS_SM, fontweight='bold', rotation=45, ha='right')
        ax.set_zorder(ax2.get_zorder() + 1)
        ax.patch.set_visible(False)

    ts_panel(gs3[0], 'Annual runoff (mm)',        CO,
             ann_ts['runoff'].tolist(),   'mm / year')
    ts_panel(gs3[1], 'Annual deep drainage (mm)', CD,
             ann_ts['drainage'].tolist(), 'mm / year')
    ann_sed_ts = ann_ts['sediment'].tolist() if 'sediment' in ann_ts.columns else [0]*len(ann_ts_idx)
    ts_panel(gs3[2], 'Annual erosion (t/ha)',      CX,
             ann_sed_ts,                 't/ha / year', '.1f')

    # Annual yield — from ann.attrs if available, also capped at MAX_TS_YEARS
    CY = '#2C7BB6'
    ann_yield_dict = ann.attrs.get('annual_yield', {}) if hasattr(ann, 'attrs') else {}
    if ann_yield_dict:
        yrs_y  = sorted(ann_yield_dict.keys())[:MAX_TS_YEARS]
        vals_y = [ann_yield_dict[y] for y in yrs_y]
        ts_panel(gs3[3], 'Annual yield (t/ha)', CY, vals_y, 't/ha / year', '.1f')
    else:
        ax_y = fig.add_subplot(gs3[3])
        ax_y.axis('off')
        ax_y.text(0.5, 0.5, 'Yield\n(no WUE/HI)',
                  ha='center', va='center', fontsize=FS_SM,
                  color=CS, transform=ax_y.transAxes)

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
    ann.attrs['annual_yield'] = df.attrs.get('annual_yield', {})
    mon     = _monthly_means(df, nyears)
    err     = (df.rain.sum() - df.runoff.sum() - df.drainage.sum()
               - df.soil_evap.sum() - df.transp.sum() - dsw) / nyears

    make_output_chart(
        ann, mon, profile, nyears, dsw, err,
        title_str    = f'Greenwood  ·  1977–1984  ({nyears} years)  ·  Balance error = {err:+.3f} mm/yr',
        out_path     = '/mnt/user-data/outputs/greenwood_standard_output.png',
        climate_name = 'Oakey Aero  (SILO P51)',
        soil_name    = profile.name,
        crop_name    = vege_obj.name,
    )
