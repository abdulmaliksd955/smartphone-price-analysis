# Smartphone Price and Specifications Analysis

CSC216 — Programming with Python course project.

## Project Idea
Analyze how smartphone specifications and brands are associated with **USA launch prices (USD)**, focusing on the relationship between RAM and price and average price differences across brands. The analysis describes associations, not causation or current retail prices.

Dataset: [Mobiles Dataset (2025)](https://www.kaggle.com/datasets/abdulmalik1518/mobiles-dataset-2025).

## Team Responsibilities

### 1. عبدالملك — Data Preparation
- Implement `load_data()` with missing-file and missing-column handling, `clean_data()`, a derived attribute, and CSV exports using Pandas.
- Use a set to identify spelling variants and a list of required columns.
- Write the dataset and cleaning sections of the report.

### 2. عبدالله — OOP & Analysis
- Implement `AnalysisTask`, `PriceSummary`, and `SpecificationComparison`, with overridden `run(data)` methods, grouped summaries, and a common polymorphic loop.
- Use a list of analysis tasks and a dictionary of results.
- Write the program-design and design-revision sections of the report.

### 3. ابراهيم — NumPy & Charts
- Build the 2D NumPy array, implement two vectorized calculations and a correlation matrix, and create at least four purposeful figures using Matplotlib and Seaborn.
- Use the correlation matrix in the heatmap and write the results and figures sections of the report.

**Shared by all three:** Agree on findings, recommendations, and limitations; maintain the README, contribution log, and AI-use log; run the complete notebook and verify results together. Every member must understand the full workflow and be able to explain a finding in the individual demonstration.

## Status
The instructor has approved the project. The data-preparation responsibility (عبدالملك) has an AI-assisted implementation and report draft; student review is not recorded yet. The team project is not complete.

| Data preparation | State |
| --- | --- |
| `load_data()`, `REQUIRED_COLUMNS` list, file/column/malformed-data errors | Done |
| Raw inspection: shape, types, missing counts, duplicates, brand variants with a set | Done |
| Raw-dataset documentation and report dataset-section draft | Done (draft) |
| `clean_data()`, numeric/unit conversions, flags for suspect facts | Done |
| Missing-value and duplicate handling, derived attribute, CSV exports | Done |
| Report cleaning section | Done (draft) |
| Student review of this part | Pending |
| عبدالله's and ابراهيم's parts, shared notebook, findings and full report | Pending |

The cleaned data covers **mixed mobile devices**, including tablets, and source facts are not independently verified: see [docs/dataset.md](docs/dataset.md).

## Cleaned Data
`--clean` writes three files to `outputs/`:

| File | Content |
| --- | --- |
| `cleaned_mobiles.csv` | 915 cleaned rows |
| `row_audit.csv` | All 930 rows with retained/flagged/excluded status |
| `cleaning_summary.csv` | Counts, missing values, ranges and units |

Main columns: `source_row`, `row_status`, `brand`, `model`, `price_usd`, `launch_year`, `ram_gb`, `battery_mah`, `screen_size_in`, `weight_g`, `price_per_gb_ram`, `quality_flags`, `format_fixes`, then the 15 raw columns. Unclear values are missing, so check for missing values before calculating. Types, units and rules are in [docs/dataset.md](docs/dataset.md).

```python
from data_preparation import load_data, clean_data, load_export
data = clean_data(load_data())                       # from the raw file
data = load_export("outputs/cleaned_mobiles.csv")    # or from the export
```

## Install, Run, Test
Tested with Python 3.14.9 and pandas 3.1.1 on Linux. From the project folder:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python data_preparation.py            # inspect the raw data
.venv/bin/python data_preparation.py --clean    # clean and write outputs/
.venv/bin/python -m unittest discover -s tests -v
```

Loading reads `data/raw.csv` locally and needs no network. Use `--output-dir FOLDER` with `--clean` to write somewhere else.

Documentation: [dataset, attribution and cleaning](docs/dataset.md), [contribution and AI-use log](docs/logs.md), TDD evidence ([part 1](docs/tdd_evidence.txt), [part 2](docs/tdd_part2_evidence.txt)), [dataset license](data/LICENSE-APACHE-2.0.txt).
