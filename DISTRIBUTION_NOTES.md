# PERFECT-Python — Distribution Readiness Review

---

## 1. Files to INCLUDE in the distribution

| File | Keep? | Notes |
|------|-------|-------|
| `waterbalance.py` | ✅ | Core engine — clean, well-commented |
| `soil.py` | ✅ | |
| `soil_xml.py` | ✅ | |
| `vege.py` | ✅ | |
| `cover_excel.py` | ✅ | |
| `perfect_io.py` | ✅ | |
| `read_p51.py` | ✅ | |
| `silo_fetch.py` | ✅ | |
| `run_simulation.py` | ✅ | |
| `output_chart.py` | ✅ | |
| `monthly_chart.py` | ✅ | |
| `input_summaries.py` | ✅ | |
| `launch.py` | ✅ | The user-facing entry point |
| `run_dalby_scenarios.py` | ✅ | Good worked example |
| `README.md` | ✅ | Update before shipping (see §4) |
| `requirements.txt` | ✅ | New — included in this folder |

## 2. Files to DELETE before distribution

| File | Reason |
|------|--------|
| `launch_1.py` | Old working copy — confusing to recipients |
| `launch_2.py` | Old working copy — confusing to recipients |

---

## 3. Code quality assessment

### ✅ Things that are solid

- **Water balance engine** (`waterbalance.py`) is clean, well-structured, and each
  function is independently testable. Science is well-documented with references.
- **Module separation** is logical — readers can follow the data flow easily.
- **Error handling** in `launch.py` is good — SILO failures, bad file paths, and
  now date-range validation all give user-friendly messages.
- **Mass balance** closes to 0.000 mm — this is the most important correctness check.
- **Chart output** degrades gracefully for long runs (8-year cap on time-series panels).

### ⚠️ Minor things worth fixing before distribution

**1. Hardcoded email in `run_dalby_scenarios.py` (line ~18)**
```python
EMAIL = 'david.freebairn@gmail.com'
```
Replace with a placeholder before distributing:
```python
EMAIL = 'your@email.com'   # ← replace with your SILO-registered email
```

**2. Hardcoded paths in `run_dalby_scenarios.py` (lines ~22-24)**
```python
SOIL_FILE  = Path(__file__).parent.parent / 'uploads' / 'Black_earth_4_layer.soil'
```
These point to your development folder structure (`/uploads/`). Recipients won't
have that layout. Change to relative paths inside the distribution folder:
```python
SOIL_FILE  = Path(__file__).parent / 'data' / 'Black_earth_4_layer.soil'
VEGE_FILE  = Path(__file__).parent / 'data' / 'wheat_stubble_incorporated.vege'
EXCEL_FILE = Path(__file__).parent / 'data' / 'Cover_data_for_Howleaky.xlsx'
```

**3. `import math` inside a hot loop**
In `waterbalance.py`, `calc_ls_factor()` does `import math` inside the function body.
The LS factor is the same every day (it's a site constant), so move the import to
the top of the file and pre-compute LS once in `daily_water_balance()` if you want
a small speed gain. For short runs it doesn't matter, but for 100-year SILO records
this saves ~36,500 redundant imports.

Fix in `waterbalance.py`:
```python
# At top of file, alongside numpy import:
import math
```
And remove the `import math` line inside `calc_ls_factor()`.

**4. Redundant `_run_daily` daily loop re-computes LS every day**
Same issue — `calc_ls_factor` is called once per day in `daily_water_balance` even
though soil slope and length never change. Pre-compute once before the loop and pass
it in, or cache it on the SoilProfile object. Low priority but easy to do.

**5. `run_simulation.py` has a bare `lambda` bare-fallow fallback**
```python
get_state = lambda doy: (0.0, 0.0, 0.0)
```
This works fine but won't carry `_wue`/`_hi` attributes. Add a named function
so it's consistent with `_make_vege_fn` and `_make_cover_fn`.

### 🔵 Not bugs — just notes

- `perfect_io.py` (`read_crp_standard`, `read_all_crp`) reads original PERFECT .CRP
  crop files but these functions aren't called anywhere in the current launcher flow.
  They're harmless to include but could be noted as "legacy/unused" in comments.
- `waterbalance.py` also exports `run_simulation()` — a simple convenience wrapper
  that isn't used by `run_simulation.py` (which has its own `_run_daily`). Fine to
  keep for users who want a simple API, just worth noting.

---

## 4. README updates needed

Before distributing, update `README.md`:
- Change the SILO email example from `david.freebairn@gmail.com` to
  `your@email.com` in all code examples (appears ~6 times).
- Update the file list in Section 2 — remove `launch_1.py`, `launch_2.py`.
- Add a one-liner note about the 8-year chart cap in the Troubleshooting section.

---

## 5. How to pack up for distribution

### Option A — Simple zip (recommended for small distribution)

1. Create a clean folder:
   ```
   PERFECT-Python/
     launch.py
     waterbalance.py
     soil.py
     soil_xml.py
     vege.py
     cover_excel.py
     perfect_io.py
     read_p51.py
     silo_fetch.py
     run_simulation.py
     output_chart.py
     monthly_chart.py
     input_summaries.py
     run_dalby_scenarios.py
     requirements.txt
     README.md
     data/
       Black_earth_4_layer.soil
       wheat_stubble_incorporated.vege
       Cover_data_for_Howleaky.xlsx
   ```
2. Zip it: right-click the folder → "Compress" (Mac) or use:
   ```bash
   zip -r PERFECT-Python-v1.0.zip PERFECT-Python/
   ```
3. Recipients unzip and run:
   ```bash
   cd PERFECT-Python
   pip install -r requirements.txt
   python launch.py
   ```

### Option B — GitHub (best for ongoing updates)

If you expect to keep improving the code and push updates to recipients:
1. Create a private GitHub repository
2. Push the clean folder as above
3. Recipients clone once:
   ```bash
   git clone https://github.com/yourname/perfect-python.git
   ```
4. Future updates they just run `git pull`

GitHub is free for private repos with up to 3 collaborators.

### Option C — PyInstaller executable (if recipients have no Python)

If recipients are not comfortable with Python at all, PyInstaller can bundle
everything into a single `.app` (Mac) or `.exe` (Windows) with Python included.
This is more work to set up but means zero installation for the end user:
```bash
pip install pyinstaller
pyinstaller --onefile launch.py
```
The output goes to `dist/launch` (Mac/Linux) or `dist/launch.exe` (Windows).
Note: you need to build separately on Mac and Windows — the binary is not
cross-platform. Also matplotlib figures may need `--windowed` flag adjustments.

**Recommendation: Option A for now.** The zip is simple, the README is clear,
and your recipients can follow the 5-step setup. Move to GitHub if/when you
start distributing updates regularly.

---

## 6. Suggested version tag

Add a single line near the top of `launch.py`:
```python
__version__ = '1.0.0'
```
And print it in the startup banner:
```python
print(f"║     PERFECT-Python  ·  Water Balance Model  v{__version__}     ║")
```
This makes it easy for recipients to report which version they're running.
