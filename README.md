# Virtual Temperature Sensing in Existing Buildings

A reproducible EnergyPlus calibration pipeline reconstructed from the Project Module **“Virtual Temperature Sensing in Existing Buildings: Calibrating EnergyPlus Models with Sparse Sensor Data.”**

The study compares a **full calibration using 10 primary-zone temperature sensors** with a **sparse calibration using 3 anchor sensors**, then treats the remaining zones as virtual temperature sensors. Calibration uses SciPy differential evolution and average per-zone RMSE.

## Pipeline

```text
model.idf
   ↓
EnergyPlus baseline simulation
   ↓
baseline/eplusout.csv
   ↓
direct synthetic-reference generator
   ↓
synthetic_reference.csv
   ├───────────────┐
   ↓               ↓
full calibration   sparse calibration
10 zones           3 anchor zones
   ↓               ↓
best model         best model
   └───────┬───────┘
           ↓
       evaluation
           ↓
primary / virtual-primary / secondary RMSE tables + figures
```

## Repository structure

```text
configs/                 Project and legacy parameter-mapping profiles
models/base/model.idf    Base EnergyPlus model
data/archive/            Archived baseline and final synthetic reference for validation
data/generated/          Generated synthetic reference
src/vts/                 Reusable Python package
outputs/                 Baseline, calibration trials, best runs, evaluation outputs
tests/                   Regression/unit tests
validation/              Numerical values reported in the submitted report
legacy/notebooks/         Key original notebooks retained only for provenance
docs/                     Submitted report and reconstruction notes
```

## Setup

The original notebooks used **EnergyPlus 25.1** and the EnergyPlus-distributed San Francisco TMY3 weather file:

`WeatherData/USA_CA_San.Francisco.Intl.AP.724940_TMY3.epw`

On Windows, with EnergyPlus installed at `C:\\EnergyPlusV25-1-0`:

```powershell
cd virtual-temperature-sensing
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

If EnergyPlus is installed elsewhere, either edit `energyplus.home` in the YAML or set:

```powershell
$env:ENERGYPLUS_HOME = "C:\EnergyPlusV25-1-0"
```

## Verify the recovered `data3` rule

This check does not require EnergyPlus; it compares the direct reference generator against the archived final `data3.csv`:

```powershell
vts --config configs/project.yaml verify-reference
```

Expected result:

```text
matches_machine_precision: true
```

## Run stage by stage

```powershell
vts --config configs/project.yaml baseline
vts --config configs/project.yaml reference
vts --config configs/project.yaml calibrate --strategy full
vts --config configs/project.yaml calibrate --strategy sparse
vts --config configs/project.yaml evaluate
```

Or run the complete workflow:

```powershell
vts --config configs/project.yaml all
```

The calibration stage executes every candidate in a **unique temporary trial directory**, logs its parameters/RMSE/audit in `optimization_history.csv`, and then explicitly reruns the optimizer's best parameter vector in `best/`. Trial folders are deleted by default after successful evaluation to avoid hundreds of megabytes of duplicate EnergyPlus files; failed trials are retained for debugging. This fixes the historical overwrite problem in the notebooks.

## Corrected vs legacy parameter mapping

The default profile uses:

```yaml
calibration:
  parameter_mapping: corrected
```

This maps the six calibration variables to active fields in the supplied IDF, including infiltration, VAV minimum flow, zone outdoor air, SAT reset setpoints, and autosized reheat sizing.

For historical comparison only:

```powershell
vts --config configs/legacy_mapping.yaml all
```

The legacy mode reproduces the original notebook field mappings, including parameters that were effectively no-ops in the supplied model. See `docs/PROVENANCE.md` before interpreting legacy results.

## Six calibration parameters

| Parameter | Bounds |
|---|---:|
| Internal gains multiplier | 0.6–1.1 |
| Infiltration multiplier | 0.5–1.5 |
| VAV minimum flow multiplier | 0.2–0.6 |
| Reheat capacity multiplier | 0.8–1.2 |
| Outdoor-air minimum flow multiplier | 0.5–1.5 |
| Supply-air temperature offset | −1.0–1.0 °C |

## Outputs

A calibration produces:

```text
outputs/calibration/full/
├── optimization_history.csv
├── best_parameters.json
├── result.json
├── trials/
│   ├── trial_0001_.../
│   ├── trial_0002_.../
│   └── ...
└── best/
    ├── best_model.idf
    ├── eplusout.csv
    ├── parameter_audit.json
    └── EnergyPlus output files
```

Evaluation produces actual zone names rather than generic “Zone 1…Zone 10” labels:

```text
outputs/evaluation/
├── summary.json
├── tables/
│   ├── primary_zones.csv
│   ├── sparse_anchor_zones.csv
│   ├── virtual_primary_zones.csv
│   └── secondary_zones.csv
└── figures/
    ├── full_primary.png
    ├── sparse_anchors.png
    ├── virtual_primary.png
    └── secondary_zones.png
```

## Historical report reference

The submitted report recorded approximately:

- full primary-zone average RMSE: **0.387 °C**;
- sparse primary-zone average RMSE: **0.392 °C**;
- sparse three-anchor calibration RMSE: **0.22 °C**;
- full secondary-zone RMSE relative to base: **0.111 °C**;
- sparse secondary-zone RMSE relative to base: **0.181 °C**;
- sensor reduction: **70%**.

These historical values are stored in `validation/report_reference.json`. They are provenance targets, not guaranteed outputs of the **corrected** parameter-mapping experiment.

## Tests

```powershell
pytest
```

The most important regression test proves that the new direct baseline → reference generator reconstructs the archived final `data3.csv` to machine precision.
