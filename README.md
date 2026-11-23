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
Proposal stage. Instructor approval and dataset-quality validation are required before full implementation.
