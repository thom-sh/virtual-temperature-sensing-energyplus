# Pipeline stages and contracts

## 1. Baseline simulation

**Input:** `models/base/model.idf` + EnergyPlus weather file  
**Output:** `outputs/baseline/eplusout.csv`

The supplied model is run with EnergyPlus using ReadVars output (`-r`). The pipeline expects hourly `Zone Mean Air Temperature` columns and a `Date/Time` column.

## 2. Synthetic reference generation

**Input:** baseline `eplusout.csv`  
**Output:** `data/generated/synthetic_reference.csv`

The final historical reference behavior is generated directly in one pass. No `data1.csv` or `data2.csv` intermediate files are created. The fixed 18-zone order in the configuration preserves the historical random-number-to-zone assignment.

## 3. Full calibration

**Calibration anchors:** all 10 primary zones.  
**Objective:** arithmetic mean of the ten individual zone RMSE values.  
**Optimizer:** SciPy differential evolution.

Each candidate gets a unique working directory. The history CSV is durable; successful trial directories are disposable by default. After optimization the best vector is always rebuilt and simulated once more in `outputs/calibration/full/best/`.

## 4. Sparse calibration

The same calibration engine is reused. The only strategy change is the anchor list:

- `PERIMETER_MID_ZN_1`
- `PERIMETER_BOT_ZN_4`
- `PERIMETER_BOT_ZN_3`

The objective is the arithmetic mean of RMSE over these three anchors. The remaining seven primary zones are not used in the objective and are later treated as virtual-sensor predictions.

## 5. Evaluation

The evaluation writes four tables:

- `primary_zones.csv` — full vs sparse RMSE for all 10 primary zones;
- `sparse_anchor_zones.csv` — the 3 sparse calibration anchors;
- `virtual_primary_zones.csv` — the 7 primary zones excluded from sparse calibration;
- `secondary_zones.csv` — the remaining 8 zones.

The final submitted report evaluated secondary zones against the uncalibrated baseline. That behavior is selectable through `evaluation.secondary_reference`. Using `synthetic_reference` instead is supported as an alternative controlled analysis.

## 6. Result outputs

`summary.json` records sensor counts, the 70% sensor reduction, average RMSE values, and sparse-vs-full percentage changes. Figures are generated automatically for the full primary set, sparse anchors, seven virtual primary zones, and eight secondary zones.
