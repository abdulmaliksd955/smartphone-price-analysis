"""Data preparation: load and inspect the raw CSV, clean it, export the result.

Inspect only:      python data_preparation.py [path/to/file.csv]
Clean and export:  python data_preparation.py --clean [--output-dir FOLDER]
The raw file and the raw DataFrame are never changed.
"""

import argparse
import csv
import hashlib
import io
import math
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

# Built from this file's location, so it works from any current directory.
DEFAULT_CSV_PATH = Path(__file__).resolve().parent / "data" / "raw.csv"

# The raw file is NOT valid UTF-8. Its only two non-ASCII bytes are 0xA5 (yen
# sign) and 0xA0 (no-break space), which Windows-1252 decodes correctly.
FILE_ENCODING = "cp1252"

# Columns our questions need: identify the phone, its USA launch price and year,
# and the specifications we may compare with price. Other columns are also kept.
REQUIRED_COLUMNS = [
    "Company Name",
    "Model Name",
    "Mobile Weight",
    "RAM",
    "Battery Capacity",
    "Screen Size",
    "Launched Price (USA)",
    "Launched Year",
]

# Cleaned numeric column: (raw column, text before number, text after number).
NUMERIC_FIELDS = {
    "price_usd": ("Launched Price (USA)", "USD", ""),
    "launch_year": ("Launched Year", "", ""),
    "ram_gb": ("RAM", "", "GB"),
    "battery_mah": ("Battery Capacity", "", "mAh"),
    "screen_size_in": ("Screen Size", "", "inches"),
    "weight_g": ("Mobile Weight", "", "g"),
}
LABEL_FIELDS = {"brand": "Company Name", "model": "Model Name"}
BRAND_LABELS = {"Poco": "POCO"}  # the only variant pair found in the raw labels
CLEAN_COLUMNS = ["source_row", "row_status", "brand", "model", *NUMERIC_FIELDS,
                 "price_per_gb_ram", "quality_flags", "format_fixes"]
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
CLEANED_FILE = "cleaned_mobiles.csv"
AUDIT_FILE = "row_audit.csv"
SUMMARY_FILE = "cleaning_summary.csv"
SUMMARY_COLUMNS = ["section", "field", "measure", "value", "unit"]
UNITS = {"price_usd": "USD", "launch_year": "year", "ram_gb": "GB",
         "battery_mah": "mAh", "screen_size_in": "inches", "weight_g": "g",
         "price_per_gb_ram": "USD per GB"}
AUDIT_COLUMNS = ["duplicate_of_source_row", *CLEAN_COLUMNS]
THOUSANDS_COMMA_FIELDS ={"price_usd", "battery_mah"}  # e.g. USD 1,099; 3,600mAh
VALID_YEARS = (1983, 2026)  # first handheld phone on sale; year of our download
PLACEHOLDERS = {"not available", "unavailable", "not announced", "unknown",
                "n/a", "na", "none", "null", "nan", "tbd", "-", "--", "?"}


def check_structure(text, path):
    """Raise ValueError if the CSV text is not a complete, regular table.

    pandas alone would skip blank lines and fill short rows with missing values,
    so every row is checked before pandas reads the text.
    """
    if not text.strip():
        raise ValueError(f"The data file is empty: {path}")

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    row_count = 0
    try:
        header = next(reader)
        missing = [name for name in REQUIRED_COLUMNS if name not in header]
        if missing:
            raise ValueError(f"Missing required columns in {path}: {missing}")
        if len(set(header)) != len(header):
            raise ValueError(f"Duplicate column names in {path}: {header}")

        for row in reader:
            if len(row) != len(header):
                raise ValueError(
                    f"Malformed CSV {path}: line {reader.line_num} has "
                    f"{len(row)} fields, expected {len(header)}")
            row_count += 1
    except csv.Error as error:
        raise ValueError(
            f"Malformed CSV {path}: line {reader.line_num}: {error}") from error

    if row_count == 0:
        raise ValueError(f"The data file has a header but no data rows: {path}")


def load_data(path=DEFAULT_CSV_PATH):
    """Return the whole raw CSV as a DataFrame of unconverted text.

    Only completely empty cells become missing values; text such as "NA" or
    "Not available" stays exactly as written.

    Raises FileNotFoundError if there is no such file, and ValueError if it is
    empty, malformed, wrongly encoded, or lacks a required column.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Data file not found: {path}")

    try:
        text = path.read_bytes().decode(FILE_ENCODING)
    except UnicodeDecodeError as error:
        raise ValueError(
            f"Cannot read {path} as {FILE_ENCODING}: {error}") from error

    check_structure(text, path)
    return pd.read_csv(io.StringIO(text, newline=""), dtype=str,
                       keep_default_na=False, na_values=[""],
                       skip_blank_lines=False)


def find_label_variants(labels):
    """Group different raw labels that match apart from case/space/punctuation.

    Example: {"poco": ["POCO", "Poco"]}. Real misspellings (different letters)
    are not guessed; check the sorted brand list by eye for those.
    """
    unique_labels = {label for label in labels if not pd.isna(label)}
    groups = {}
    for label in unique_labels:
        key = "".join(char for char in label.casefold() if char.isalnum())
        groups.setdefault(key, set()).add(label)
    return {key: sorted(group) for key, group in sorted(groups.items())
            if len(group) > 1}


def inspect_data(data):
    """Return a dictionary describing the raw data. The data is not changed."""
    not_available = (data == "Not available").sum()
    brands = data["Company Name"]
    return {
        "shape": data.shape,
        "columns": data.columns.tolist(),
        "dtypes": {name: str(dtype) for name, dtype in data.dtypes.items()},
        "missing_counts": {name: int(n) for name, n in data.isna().sum().items()},
        # Text placeholders are not counted as missing by pandas.
        "not_available_counts": {name: int(n) for name, n in not_available.items()
                                 if n > 0},
        # Repeats after the first copy of a completely identical row.
        "duplicate_rows": int(data.duplicated().sum()),
        "brand_labels": sorted(set(brands.dropna())),
        "brand_variants": find_label_variants(brands),
    }


def blank_reason(text):
    """Return "missing", "placeholder", or "" when the cell has real content."""
    if pd.isna(text) or not str(text).strip():
        return "missing"
    if str(text).strip().casefold() in PLACEHOLDERS:
        return "placeholder"
    return ""


def parse_number(field, text):
    """Return (number, "") for one clear value, or (None, reason) otherwise.

    Nothing is guessed: text that could be read in two ways has no number.
    """
    reason = blank_reason(text)
    if reason:
        return None, reason

    text = str(text).strip()
    if len(re.findall(r"[0-9][0-9.,]*", text)) > 1:
        return None, "multiple_values"          # 8GB / 12GB

    _, before, after = NUMERIC_FIELDS[field]
    match = re.fullmatch(
        rf"{before}\s*(-?[0-9][0-9,]*(?:\.[0-9]+)?)\s*{after}\s*(\(.*\))?",
        text, re.IGNORECASE)
    if not match:
        return None, "unexpected_format"        # wrong unit or currency
    if match.group(2):
        return None, "qualified_value"          # 8.0 inches (unfolded)

    # A comma must separate groups of three digits, and only where the source
    # uses it that way. Three digits after a dot could also mean thousands.
    digits = match.group(1)
    plain = re.fullmatch(r"-?[0-9]+(\.[0-9]{1,2})?", digits)
    grouped = re.fullmatch(r"-?[1-9][0-9]{0,2}(,[0-9]{3})+(\.[0-9]{1,2})?", digits)
    if not plain and not (grouped and field in THOUSANDS_COMMA_FIELDS):
        return None, "ambiguous_separator"      # USD 396,22

    number = float(digits.replace(",", ""))
    if number <= 0:
        return None, "not_positive"
    if math.isinf(number):
        return None, "out_of_range"             # hundreds of digits
    if field == "launch_year":
        first, last = VALID_YEARS
        if not (number.is_integer() and first <= number <= last):
            return None, "out_of_range"
    return number, ""


def clean_label(text):
    """Return (label, reason, fix) with tidy spaces and one brand spelling."""
    reason = blank_reason(text)
    if reason:
        return None, reason, ""
    label = " ".join(str(text).split())
    fix = "" if label == text else "spaces_tidied"
    return label, "", fix


def clean_row(raw_row):
    """Return a dictionary of cleaned values and visible notes for one raw row."""
    cleaned, flags, fixes = {}, [], []

    for field, column in LABEL_FIELDS.items():
        label, reason, fix = clean_label(raw_row[column])
        if field == "brand" and label in BRAND_LABELS:
            label, fix = BRAND_LABELS[label], "label_unified"
        cleaned[field] = label
        if reason:
            flags.append(f"{field}:{reason}")
        if fix:
            fixes.append(f"{field}:{fix}")

    for field, (column, _, _) in NUMERIC_FIELDS.items():
        number, reason = parse_number(field, raw_row[column])
        cleaned[field] = number
        if reason:
            flags.append(f"{field}:{reason}")
        elif "," in str(raw_row[column]):
            fixes.append(f"{field}:comma_removed")

    # Safe: parse_number never returns zero or a negative RAM value. The result
    # can still be too large for a number (infinity), which is not a real ratio.
    ratio = None
    if cleaned["price_usd"] is not None and cleaned["ram_gb"] is not None:
        ratio = cleaned["price_usd"] / cleaned["ram_gb"]
        if math.isinf(ratio):
            ratio = None
            flags.append("price_per_gb_ram:not_finite")
    cleaned["price_per_gb_ram"] = ratio

    # Review hints only: the row is kept and its values are not corrected.
    model = cleaned["model"] or ""
    if "Pad" in model or "Tab" in model:
        flags.append("model:tablet_like_name")
    if (cleaned["brand"] == "Apple" and cleaned["weight_g"] == 174
            and re.fullmatch(r"iPhone 16 [0-9]+GB", model)):
        flags.append("source:iphone16_specs_disputed")  # see docs/dataset.md

    cleaned["quality_flags"] = ";".join(flags)
    cleaned["format_fixes"] = ";".join(fixes)
    return cleaned


def check_raw_frame(raw):
    """Raise ValueError if the DataFrame cannot be cleaned."""
    missing = [name for name in REQUIRED_COLUMNS if name not in raw.columns]
    if missing:
        raise ValueError(f"Cannot clean data, missing required columns: {missing}")
    if not raw.columns.is_unique:
        raise ValueError(f"Duplicate column names: {raw.columns.tolist()}")
    clash = [name for name in AUDIT_COLUMNS if name in raw.columns]
    if clash:
        raise ValueError(f"Raw columns use reserved cleaned names: {clash}")
    if raw.empty:
        raise ValueError("Cannot clean data: there are no data rows")


def find_first_copies(records):
    """For each row, return the source_row of its earlier exact copy, or None."""
    first_seen, originals = {}, []
    for source_row, record in enumerate(records, start=1):
        key = tuple(None if pd.isna(value) else value for value in record.values())
        originals.append(first_seen.get(key))
        first_seen.setdefault(key, source_row)
    return originals


def audit_rows(raw):
    """Return every raw row with its cleaned values and what happened to it.

    Cleaned columns come first, then every raw column unchanged. source_row is
    the 1-based position of the row in the given raw data (header not counted).
    The raw DataFrame is not changed.
    """
    check_raw_frame(raw)
    raw = raw.reset_index(drop=True)
    records = raw.to_dict("records")
    cleaned = pd.DataFrame([clean_row(record) for record in records])
    cleaned["source_row"] = range(1, len(raw) + 1)
    cleaned["duplicate_of_source_row"] = pd.array(find_first_copies(records),
                                                  dtype="Int64")
    cleaned["row_status"] = "retained"
    cleaned.loc[cleaned["quality_flags"] != "", "row_status"] = "retained_flagged"
    cleaned.loc[cleaned["duplicate_of_source_row"].notna(),
                "row_status"] = "excluded_duplicate"
    for field in UNITS:  # every numeric column, including the ratio
        cleaned[field] = cleaned[field].astype("float64")
    cleaned["launch_year"] = cleaned["launch_year"].astype("Int64")
    return pd.concat([cleaned[AUDIT_COLUMNS], raw], axis=1)


def clean_data(raw):
    """Return the cleaned rows (a new DataFrame) without exact raw repeats."""
    audit = audit_rows(raw)
    kept = audit[audit["row_status"] != "excluded_duplicate"]
    return kept.drop(columns="duplicate_of_source_row").reset_index(drop=True)


def count_notes(column):
    """Count each "field:reason" note in a quality_flags/format_fixes column."""
    notes = [note for text in column for note in text.split(";") if note]
    return sorted(Counter(notes).items())


def summarize_cleaning(audit):
    """Return cleaning checks as a table: section, field, measure, value, unit.

    It counts all raw rows for "raw" measures and only kept rows otherwise.
    Ranges are checks on the cleaning, not research results.
    """
    status = audit["row_status"]
    kept = audit[status != "excluded_duplicate"]
    table = [("rows", "all", "raw", len(audit), "rows"),
             ("rows", "all", "excluded_duplicate",
              (status == "excluded_duplicate").sum(), "rows"),
             ("rows", "all", "cleaned", len(kept), "rows"),
             ("rows", "all", "retained", (status == "retained").sum(), "rows"),
             ("rows", "all", "retained_flagged",
              (status == "retained_flagged").sum(), "rows")]

    raw_columns = dict(LABEL_FIELDS)
    raw_columns.update({field: spec[0] for field, spec in NUMERIC_FIELDS.items()})
    for field, column in raw_columns.items():
        blanks = sum(blank_reason(text) != "" for text in audit[column])
        table.append(("missing", field, "raw_blank_or_placeholder", blanks, "rows"))
        table.append(("missing", field, "cleaned_missing",
                      kept[field].isna().sum(), "rows"))
    table.append(("missing", "price_per_gb_ram", "cleaned_missing",
                  kept["price_per_gb_ram"].isna().sum(), "rows"))

    for field, unit in UNITS.items():
        values = kept[field].dropna()
        table.append(("range", field, "min", "" if values.empty else values.min(), unit))
        table.append(("range", field, "max", "" if values.empty else values.max(), unit))

    for section, column in [("quality_flag", "quality_flags"),
                            ("format_fix", "format_fixes")]:
        for note, count in count_notes(kept[column]):
            field, measure = note.split(":")
            table.append((section, field, measure, count, "rows"))

    # Text values, so pandas does not turn counts into decimals (5 into 5.0).
    table = [(section, field, measure, str(value), unit)
             for section, field, measure, value, unit in table]
    return pd.DataFrame(table, columns=SUMMARY_COLUMNS)


def check_export_target(path, columns):
    """Raise FileExistsError unless path is free or is our own earlier export."""
    if not path.exists() and not path.is_symlink():
        return
    header = ",".join(columns).encode()
    if (path.is_symlink() or not path.is_file()
            or not path.read_bytes().startswith((header + b",", header + b"\n"))):
        raise FileExistsError(
            f"Not overwriting {path}: it does not look like an earlier export. "
            "Move it or choose another output folder.")


def export_results(raw_path=DEFAULT_CSV_PATH, output_dir=DEFAULT_OUTPUT_DIR):
    """Clean the raw file, write three managed CSV files, return the summary.

    Only files with the three managed names are ever written, and every check
    is done before the first write. The raw file is only read.
    """
    raw_path, output_dir = Path(raw_path), Path(output_dir)
    raw_folders = {raw_path.resolve().parent, DEFAULT_CSV_PATH.parent}
    if output_dir.resolve() in raw_folders:
        raise ValueError(f"Choose an output folder that is not a raw data folder: "
                         f"{output_dir}")

    raw = load_data(raw_path)
    audit, cleaned = audit_rows(raw), clean_data(raw)
    if cleaned["price_usd"].isna().all():
        raise ValueError(f"No usable USA price was found in {raw_path}; "
                         "nothing was exported")
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    source = pd.DataFrame([("source", "raw_file", "sha256", digest, "")],
                          columns=SUMMARY_COLUMNS)
    summary = pd.concat([source, summarize_cleaning(audit)], ignore_index=True)

    exports = [(output_dir / CLEANED_FILE, cleaned, CLEAN_COLUMNS),
               (output_dir / AUDIT_FILE, audit, AUDIT_COLUMNS),
               (output_dir / SUMMARY_FILE, summary, SUMMARY_COLUMNS)]
    for path, _, columns in exports:
        check_export_target(path, columns)
    output_dir.mkdir(parents=True, exist_ok=True)
    for path, table, _ in exports:
        path.write_bytes(table.to_csv(index=False, lineterminator="\n")
                         .encode("utf-8"))
    return summary


def load_export(path):
    """Read an exported cleaned or audit CSV back with the documented types.

    Raw columns stay text, so a raw "NA" or "2024" is not reinterpreted.
    """
    data = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    for field in UNITS:
        data[field] = data[field].astype("float64")
    for field in ("source_row", "launch_year", "duplicate_of_source_row"):
        if field in data:
            data[field] = data[field].astype("float64").astype("Int64")
    for field in ("quality_flags", "format_fixes"):
        data[field] = data[field].fillna("")
    return data


def print_report(report):
    rows, columns = report["shape"]
    print(f"Shape: {rows} rows x {columns} columns")
    print("\nColumn (type): missing cells")
    for name in report["columns"]:
        print(f"  {name} ({report['dtypes'][name]}): "
              f"{report['missing_counts'][name]}")
    print(f"\n'Not available' text cells: {report['not_available_counts']}")
    print(f"Exact duplicate rows (after the first copy): {report['duplicate_rows']}")
    print(f"\nRaw brand labels ({len(report['brand_labels'])}): "
          f"{report['brand_labels']}")
    print(f"Brand spelling/case/space variants: {report['brand_variants']}")


def main():
    parser = argparse.ArgumentParser(description="Inspect or clean the raw phone CSV.")
    parser.add_argument("path", nargs="?", default=DEFAULT_CSV_PATH,
                        help="raw CSV file (default: data/raw.csv)")
    parser.add_argument("--clean", action="store_true",
                        help="clean the data and write the CSV exports")
    parser.add_argument("--output-dir",
                        help="folder for the exports (default: outputs/)")
    options = parser.parse_args()
    if options.output_dir is not None and not options.clean:
        parser.error("--output-dir can only be used together with --clean")

    try:
        if options.clean:
            output_dir = options.output_dir or DEFAULT_OUTPUT_DIR
            summary = export_results(options.path, output_dir)
            print(summary.to_string(index=False))
            print(f"\nWrote {CLEANED_FILE}, {AUDIT_FILE} and {SUMMARY_FILE} "
                  f"to {output_dir}")
        else:
            print_report(inspect_data(load_data(options.path)))
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
