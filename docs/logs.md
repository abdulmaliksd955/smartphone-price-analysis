# Contribution and AI-use log

## Contributions

| Date | Responsibility | Work | Status |
| --- | --- | --- | --- |
| 2026-11-25 | عبدالملك — Data Preparation, part 1 | Raw CSV obtained by Hermes Agent (AI); loading, raw inspection, tests, and dataset documentation drafted by Claude Code (AI) | On branch `hermes/abdulmalik-data-prep-part1`, not committed; student review not recorded |
| 2026-11-25 | عبدالملك — Data Preparation, part 2 | Cleaning, derived attribute, CSV exports, tests, dataset license file and attribution, and cleaning report draft prepared by Claude Code (AI) | Same branch, not committed; student review not recorded |

The responsibility column shows whose project part this is, not who wrote the code.
No work by عبدالله or ابراهيم is included in these entries.

## AI use

| Date | Tool | What it did | Checks actually run |
| --- | --- | --- | --- |
| 2026-11-25 | Hermes Agent | Scoped the half-task; created the independent branch; used an anonymous live Kaggle browser session to verify the current Apache 2.0 card and download the original Version 1 ZIP (the public same-origin download succeeded; direct server requests returned 404); prepared the isolated environment; delegated the implementation to Claude Code | Independently reran the 22 unit tests (passed), the real-data demo, and the original file's SHA-256 check |
| 2026-11-25 | Claude Code (Claude Opus 5.5), working from a detailed written task | Wrote `data_preparation.py`, the tests, `docs/`, `requirements.txt`, `.gitignore`, `.gitattributes`, and the README update. Inspected `data/raw.csv` read-only | 22 unit tests (failing first, then passing; see `tdd_evidence.txt`), the demo on the real file, and the file hash |
| 2026-11-25 | Hermes Agent (part 2) | Wrote the scope and instructions for part 2 and delegated the implementation to Claude Code; found the ratio overflow bug and requested the fix | Reported: the 22 part 1 tests passing before part 2 started; then, before the overflow fix, an independent full run of 58 tests (exit 0) and the real `--clean` run (exit 0; 930 to 915 rows, 15 repeats, 807 retained, 108 flagged, 912 ratios). Readback and checks after the fix are not recorded yet |
| 2026-11-25 | Claude Code (Claude Opus 5.5) (part 2) | Added cleaning and exports to `data_preparation.py`; wrote `tests/test_data_cleaning.py`, `data/LICENSE-APACHE-2.0.txt`, `data/ATTRIBUTION.md`, `docs/tdd_part2_evidence.txt`, the cleaning documentation, and the README update; generated `outputs/` from the real file; fixed the ratio overflow | Unit tests written first for each step (see `tdd_part2_evidence.txt`), the full test suite (59 tests after the fix), the real `--clean` run with readback, and the raw file hash |

- The code and report draft are AI-written. Student review has not been recorded
  yet; the student must read, understand, and adapt them before submission.
- Claude Code did not access the network in part 1. In part 2 its only network
  access was reading the Apache license text from apache.org. The download and
  dataset license details come from Hermes Agent's Kaggle session, and the Apple
  comparison was supplied in the task; Claude Code did not recheck them online.
- The Hermes Agent entries are recorded as reported in the tasks.
- Synthetic rows appear only in the tests and are not used as findings.
