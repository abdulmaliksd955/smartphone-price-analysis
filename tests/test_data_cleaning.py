"""Tests for data_preparation.py (part 2: cleaning and CSV exports).

Only classes whose name starts with "Real" read data/raw.csv. Every other class
uses SYNTHETIC values invented for testing; they are not findings about phones.
"""

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import data_preparation as dp  # noqa: E402


class ParseNumberTests(unittest.TestCase):
    def test_documented_units_separators_and_decimals(self):
        cases = [
            ("price_usd", "USD 799", 799.0),
            ("price_usd", "USD 1,099", 1099.0),
            ("price_usd", "USD 634.99", 634.99),
            ("price_usd", " usd 1,234,567.50 ", 1234567.5),
            ("ram_gb", "1.5GB", 1.5),
            ("ram_gb", "8 gb", 8.0),
            ("battery_mah", "3,600mAh", 3600.0),
            ("battery_mah", "5000mAh", 5000.0),
            ("screen_size_in", "6.78 inches", 6.78),
            ("weight_g", "300.5g", 300.5),
            ("launch_year", "2024", 2024.0),
        ]
        for field, text, expected in cases:
            with self.subTest(field=field, text=text):
                self.assertEqual(dp.parse_number(field, text), (expected, ""))

    def test_wrong_currency_or_unit_is_not_converted(self):
        cases = [("price_usd", "AED 2,799"), ("price_usd", "$799"),
                 ("price_usd", "799"), ("ram_gb", "512MB"), ("ram_gb", "8"),
                 ("weight_g", "6oz"), ("weight_g", "1kg")]
        for field, text in cases:
            with self.subTest(field=field, text=text):
                self.assertEqual(dp.parse_number(field, text),
                                 (None, "unexpected_format"))

    def test_unclear_values_become_missing_with_a_reason(self):
        cases = [
            ("price_usd", None, "missing"),
            ("price_usd", float("nan"), "missing"),
            ("ram_gb", "  ", "missing"),
            ("price_usd", "Not available", "placeholder"),
            ("ram_gb", "N/A", "placeholder"),
            ("weight_g", "-", "placeholder"),
            ("price_usd", "USD 396,22", "ambiguous_separator"),
            ("price_usd", "USD 1,0999", "ambiguous_separator"),
            ("price_usd", "USD 0,999", "ambiguous_separator"),
            ("price_usd", "USD 1.099", "ambiguous_separator"),
            ("battery_mah", "5.000mAh", "ambiguous_separator"),
            ("screen_size_in", "6,78 inches", "ambiguous_separator"),
            ("screen_size_in", "6,781 inches", "ambiguous_separator"),
            ("ram_gb", "1,5GB", "ambiguous_separator"),
            ("ram_gb", "8GB / 12GB", "multiple_values"),
            ("price_usd", "USD 999 - 1,099", "multiple_values"),
            ("screen_size_in", "6.7 inches (main), 2.7 inches (external)",
             "multiple_values"),
            ("screen_size_in", "8.0 inches (unfolded)", "qualified_value"),
            ("ram_gb", "0GB", "not_positive"),
            ("ram_gb", "-4GB", "not_positive"),
            ("price_usd", "USD 0.00", "not_positive"),
            ("price_usd", "USD -5", "not_positive"),
            ("ram_gb", "1.2.3GB", "unexpected_format"),
            ("ram_gb", "٨GB", "unexpected_format"),
            ("launch_year", "2,024", "ambiguous_separator"),
            ("launch_year", "24", "out_of_range"),
            ("launch_year", "2024.5", "out_of_range"),
            ("launch_year", "9999", "out_of_range"),
            ("ram_gb", "9" * 400 + "GB", "out_of_range"),  # would become infinity
        ]
        for field, text, reason in cases:
            with self.subTest(field=field, text=text):
                self.assertEqual(dp.parse_number(field, text), (None, reason))


def make_raw(*changes):
    """Return SYNTHETIC raw rows: one good row, changed by each given dict."""
    good = {"Company Name": "TestCo", "Model Name": "Alpha 1", "RAM": "8GB",
            "Mobile Weight": "180.5g", "Battery Capacity": "5,000mAh",
            "Screen Size": "6.5 inches", "Launched Price (USA)": "USD 1,000",
            "Launched Year": "2024", "Extra": "note"}
    return pd.DataFrame([{**good, **change} for change in changes], dtype=object)


class CleanDataTests(unittest.TestCase):
    def test_schema_units_and_raw_context(self):
        raw = make_raw({})
        clean = dp.clean_data(raw)
        self.assertEqual(clean.columns.tolist(),
                         dp.CLEAN_COLUMNS + raw.columns.tolist())
        row = clean.iloc[0]
        self.assertEqual(row["source_row"], 1)
        self.assertEqual((row["brand"], row["model"]), ("TestCo", "Alpha 1"))
        self.assertEqual(row["price_usd"], 1000.0)
        self.assertEqual(row["launch_year"], 2024)
        self.assertEqual(row["ram_gb"], 8.0)
        self.assertEqual(row["battery_mah"], 5000.0)
        self.assertEqual(row["screen_size_in"], 6.5)
        self.assertEqual(row["weight_g"], 180.5)
        self.assertEqual(row["Launched Price (USA)"], "USD 1,000")  # raw kept
        self.assertEqual(row["Extra"], "note")

    def test_brand_and_model_labels(self):
        clean = dp.clean_data(make_raw(
            {"Company Name": "Poco"}, {"Company Name": " POCO "},
            {"Company Name": "iQOO", "Model Name": " Alpha  2 "},
            {"Company Name": None}, {"Model Name": "Not available"}))
        self.assertEqual(clean["brand"].tolist()[:3], ["POCO", "POCO", "iQOO"])
        self.assertEqual(clean["model"][2], "Alpha 2")
        self.assertTrue(pd.isna(clean["brand"][3]))
        self.assertTrue(pd.isna(clean["model"][4]))

    def test_quality_flags_are_separate_from_format_fixes(self):
        clean = dp.clean_data(make_raw(
            {"Company Name": "Poco"},
            {"Launched Price (USA)": "USD 396,22", "RAM": "8GB / 12GB"},
            {"Company Name": "-", "Battery Capacity": "5000mAh",
             "Launched Price (USA)": "USD 634.99"}))
        self.assertEqual(clean["quality_flags"].tolist(), [
            "", "price_usd:ambiguous_separator;ram_gb:multiple_values",
            "brand:placeholder"])
        self.assertEqual(clean["format_fixes"].tolist(), [
            "brand:label_unified;price_usd:comma_removed;battery_mah:comma_removed",
            "battery_mah:comma_removed", ""])
        self.assertTrue(pd.isna(clean["price_usd"][1]))
        self.assertTrue(pd.isna(clean["ram_gb"][1]))
        self.assertEqual(clean["price_usd"][2], 634.99)

    def test_input_is_not_changed(self):
        raw = make_raw({"Company Name": "Poco"}, {"RAM": None})
        before = raw.copy(deep=True)
        dp.clean_data(raw)
        pd.testing.assert_frame_equal(raw, before)

    def test_missing_or_repeated_columns_and_empty_input(self):
        raw = make_raw({})
        with self.assertRaisesRegex(ValueError, "RAM.*Screen Size"):
            dp.clean_data(raw.drop(columns=["RAM", "Screen Size"]))
        with self.assertRaisesRegex(ValueError, "(?i)duplicate column"):
            dp.clean_data(pd.concat([raw, raw[["RAM"]]], axis=1))
        with self.assertRaisesRegex(ValueError, "brand"):
            dp.clean_data(raw.rename(columns={"Extra": "brand"}))
        with self.assertRaisesRegex(ValueError, "(?i)no data rows"):
            dp.clean_data(raw.iloc[:0])


class PricePerGbTests(unittest.TestCase):
    def test_ratio_is_usd_divided_by_gb(self):
        clean = dp.clean_data(make_raw(
            {}, {"RAM": "1.5GB", "Launched Price (USA)": "USD 129"}))
        self.assertEqual(clean["price_per_gb_ram"].tolist(), [125.0, 86.0])

    def test_ratio_is_missing_when_an_input_is_missing_zero_or_negative(self):
        clean = dp.clean_data(make_raw(
            {"RAM": "0GB"}, {"RAM": "-4GB"}, {"RAM": None},
            {"RAM": "8GB / 12GB"}, {"Launched Price (USA)": "USD 396,22"}))
        self.assertTrue(clean["price_per_gb_ram"].isna().all())

    def test_ratio_too_large_for_a_number_is_missing_with_a_reason(self):
        clean = dp.clean_data(make_raw(
            {"RAM": "0.01GB", "Launched Price (USA)": "USD " + "9" * 308}, {}))
        self.assertTrue(pd.notna(clean["price_usd"][0]))  # the inputs are finite
        self.assertEqual(clean["ram_gb"][0], 0.01)
        self.assertTrue(pd.isna(clean["price_per_gb_ram"][0]))
        self.assertEqual(clean["quality_flags"].tolist(),
                         ["price_per_gb_ram:not_finite", ""])
        self.assertEqual(clean["row_status"].tolist(),
                         ["retained_flagged", "retained"])
        self.assertEqual(clean["price_per_gb_ram"][1], 125.0)


class DuplicateTests(unittest.TestCase):
    def setUp(self):
        self.raw = make_raw(
            {"RAM": None},                       # 1 first copy, flagged
            {"Model Name": "Alpha 1 256GB"},     # 2 storage variant
            {"RAM": None},                       # 3 exact repeat of row 1
            {"RAM": None, "Extra": "other"},     # 4 differs in one raw column
            {"Company Name": "POCO"},            # 5
            {"Company Name": "Poco"},            # 6 same only after cleaning
            {"RAM": None})                       # 7 exact repeat of row 1

    def test_only_exact_raw_repeats_are_excluded(self):
        clean = dp.clean_data(self.raw)
        self.assertEqual(clean["source_row"].tolist(), [1, 2, 4, 5, 6])
        self.assertEqual(clean.index.tolist(), [0, 1, 2, 3, 4])
        self.assertEqual(clean["row_status"].tolist(), [
            "retained_flagged", "retained", "retained_flagged",
            "retained", "retained"])

    def test_audit_keeps_every_row_with_its_status(self):
        audit = dp.audit_rows(self.raw)
        self.assertEqual(audit["source_row"].tolist(), [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(audit["row_status"].tolist(), [
            "retained_flagged", "retained", "excluded_duplicate",
            "retained_flagged", "retained", "retained", "excluded_duplicate"])
        self.assertEqual(audit["duplicate_of_source_row"].dropna().tolist(), [1, 1])
        pd.testing.assert_frame_equal(audit[self.raw.columns.tolist()], self.raw)

    def test_source_rows_do_not_depend_on_the_index(self):
        shuffled_index = self.raw.set_index(pd.Index([9, 9, 3, 0, 1, 2, 5]))
        self.assertEqual(dp.clean_data(shuffled_index)["source_row"].tolist(),
                         [1, 2, 4, 5, 6])


class SourceCaveatTests(unittest.TestCase):
    def test_tablet_like_names_are_flagged_but_kept(self):
        names = ["iPad Test", "Galaxy Tab Test", "Pad 9", "MatePad 1", "Alpha 1"]
        clean = dp.clean_data(make_raw(*[{"Model Name": name} for name in names]))
        self.assertEqual(clean["model"].tolist(), names)
        self.assertEqual(clean["quality_flags"].tolist(),
                         ["model:tablet_like_name"] * 4 + [""])

    def test_disputed_iphone_16_weight_is_flagged_not_corrected(self):
        iphone = {"Company Name": "Apple", "Mobile Weight": "174g"}
        clean = dp.clean_data(make_raw(
            {**iphone, "Model Name": "iPhone 16 128GB"},
            {**iphone, "Model Name": "iPhone 16 Plus 128GB"},
            {**iphone, "Model Name": "iPhone 16 128GB", "Mobile Weight": "170g"}))
        self.assertEqual(clean["weight_g"].tolist(), [174.0, 174.0, 170.0])
        self.assertEqual(clean["quality_flags"].tolist(),
                         ["source:iphone16_specs_disputed", "", ""])


class SummaryTests(unittest.TestCase):
    def setUp(self):
        audit = dp.audit_rows(make_raw(
            {}, {},                                  # row 2 repeats row 1
            {"RAM": "2GB", "Launched Price (USA)": "USD 100"},
            {"RAM": None, "Launched Price (USA)": "Not available"},
            {"RAM": "8GB / 12GB", "Company Name": "Poco"}))
        self.summary = dp.summarize_cleaning(audit)

    def value(self, section, field, measure):
        row = self.summary.query(
            "section == @section and field == @field and measure == @measure")
        self.assertEqual(len(row), 1, (section, field, measure))
        return row["value"].iloc[0]

    def test_row_counts_before_and_after(self):
        expected = {"raw": 5, "excluded_duplicate": 1, "cleaned": 4,
                    "retained": 2, "retained_flagged": 2}
        for measure, count in expected.items():
            self.assertEqual(self.value("rows", "all", measure), str(count))

    def test_missing_before_and_after_and_ranges(self):
        self.assertEqual(self.value("missing", "ram_gb", "raw_blank_or_placeholder"), "1")
        self.assertEqual(self.value("missing", "ram_gb", "cleaned_missing"), "2")
        self.assertEqual(self.value("missing", "price_usd", "raw_blank_or_placeholder"), "1")
        self.assertEqual(self.value("missing", "brand", "cleaned_missing"), "0")
        self.assertEqual(self.value("missing", "price_per_gb_ram", "cleaned_missing"), "2")
        self.assertEqual(self.value("range", "price_usd", "min"), "100.0")
        self.assertEqual(self.value("range", "price_usd", "max"), "1000.0")
        self.assertEqual(self.value("range", "launch_year", "max"), "2024")
        units = self.summary[self.summary["section"] == "range"]
        units = dict(zip(units["field"], units["unit"]))
        self.assertEqual(units["price_per_gb_ram"], "USD per GB")
        self.assertEqual(units["battery_mah"], "mAh")

    def test_flags_and_fixes_are_counted_in_cleaned_rows_only(self):
        self.assertEqual(self.value("quality_flag", "ram_gb", "multiple_values"), "1")
        self.assertEqual(self.value("quality_flag", "price_usd", "placeholder"), "1")
        self.assertEqual(self.value("format_fix", "brand", "label_unified"), "1")
        self.assertEqual(self.value("format_fix", "battery_mah", "comma_removed"), "4")

    def test_column_without_any_number_has_an_empty_range(self):
        summary = dp.summarize_cleaning(dp.audit_rows(make_raw({"RAM": None})))
        ram = summary.query("section == 'range' and field == 'ram_gb'")
        self.assertEqual(ram["value"].tolist(), ["", ""])


class ExportTests(unittest.TestCase):
    """SYNTHETIC raw files in a temporary folder; never project outputs/."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.raw_path = self.folder / "in" / "synthetic.csv"
        self.raw_path.parent.mkdir()
        make_raw({}, {}, {"RAM": "1.5GB", "Launched Price (USA)": "USD 634.99"},
                 {"Company Name": "NA", "Extra": "¥ a,b"}).to_csv(
            self.raw_path, index=False, encoding=dp.FILE_ENCODING)
        self.raw_bytes = self.raw_path.read_bytes()
        self.out = self.folder / "out"

    def read_outputs(self):
        return {path.name: path.read_bytes() for path in self.out.iterdir()}

    def test_readback_equals_the_cleaned_data(self):
        dp.export_results(self.raw_path, self.out)
        clean = dp.clean_data(dp.load_data(self.raw_path))
        back = dp.load_export(self.out / dp.CLEANED_FILE)
        self.assertEqual(back.columns.tolist(), clean.columns.tolist())
        pd.testing.assert_frame_equal(back, clean, check_dtype=False)
        self.assertEqual(back["Company Name"].tolist()[-1], "NA")
        self.assertEqual(back["Extra"].tolist()[-1], "¥ a,b")
        audit = dp.load_export(self.out / dp.AUDIT_FILE)
        self.assertEqual(audit["source_row"].tolist(), [1, 2, 3, 4])
        self.assertEqual(audit["row_status"][1], "excluded_duplicate")

    def test_repeat_export_is_identical_and_raw_is_untouched(self):
        dp.export_results(self.raw_path, self.out)
        first = self.read_outputs()
        (self.out / "teammate.csv").write_bytes(b"keep me")
        dp.export_results(self.raw_path, self.out)
        self.assertEqual(self.read_outputs(), {**first, "teammate.csv": b"keep me"})
        self.assertEqual(set(first),
                         {dp.CLEANED_FILE, dp.AUDIT_FILE, dp.SUMMARY_FILE})
        self.assertEqual(self.raw_path.read_bytes(), self.raw_bytes)

    def test_unrelated_file_with_a_managed_name_stops_everything(self):
        self.out.mkdir()
        other = self.out / dp.SUMMARY_FILE
        for content in (b"my,own,notes\n1,2,3\n", b""):
            with self.subTest(content=content):
                other.write_bytes(content)
                with self.assertRaisesRegex(FileExistsError, dp.SUMMARY_FILE):
                    dp.export_results(self.raw_path, self.out)
                self.assertEqual(self.read_outputs(), {dp.SUMMARY_FILE: content})

    def test_links_and_folders_with_managed_names_are_refused(self):
        self.out.mkdir()
        target = self.out / dp.CLEANED_FILE
        target.symlink_to(self.raw_path)
        with self.assertRaises(FileExistsError):
            dp.export_results(self.raw_path, self.out)
        target.unlink()
        target.mkdir()
        with self.assertRaises(FileExistsError):
            dp.export_results(self.raw_path, self.out)
        self.assertEqual(self.raw_path.read_bytes(), self.raw_bytes)

    def test_raw_folders_are_not_allowed_as_output(self):
        for folder in (self.raw_path.parent, dp.DEFAULT_CSV_PATH.parent):
            with self.subTest(folder=folder):
                with self.assertRaisesRegex(ValueError, "(?i)raw data folder"):
                    dp.export_results(self.raw_path, folder)
        self.assertEqual(list(self.raw_path.parent.iterdir()), [self.raw_path])

    def test_result_without_any_usable_price_is_not_exported(self):
        make_raw({"Launched Price (USA)": "USD 396,22"}).to_csv(
            self.raw_path, index=False)
        with self.assertRaisesRegex(ValueError, "(?i)no usable"):
            dp.export_results(self.raw_path, self.out)
        self.assertFalse(self.out.exists())


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        (self.folder / "in").mkdir()
        self.raw_path = self.folder / "in" / "synthetic.csv"
        make_raw({}, {}).to_csv(self.raw_path, index=False)
        self.out = self.folder / "out"

    def run_program(self, *arguments):
        return subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "data_preparation.py"),
             *map(str, arguments)],
            cwd=self.folder, capture_output=True, text=True)

    def test_clean_mode_writes_exports_and_prints_the_summary(self):
        done = self.run_program(self.raw_path, "--clean", "--output-dir", self.out)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((self.out / dp.CLEANED_FILE).is_file())
        self.assertIn("excluded_duplicate", done.stdout)
        self.assertIn(dp.CLEANED_FILE, done.stdout)

    def test_inspection_mode_writes_nothing(self):
        done = self.run_program(self.raw_path)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("2 rows x 9 columns", done.stdout)
        self.assertEqual(list(self.folder.iterdir()), [self.raw_path.parent])

    def test_output_dir_needs_clean(self):
        done = self.run_program(self.raw_path, "--output-dir", self.out)
        self.assertEqual(done.returncode, 2)
        self.assertIn("--clean", done.stderr)
        self.assertFalse(self.out.exists())

    def test_clean_errors_have_no_traceback(self):
        done = self.run_program(self.raw_path, "--clean", "--output-dir",
                                self.raw_path.parent)
        self.assertEqual(done.returncode, 1)
        self.assertIn("raw data folder", done.stderr)
        self.assertNotIn("Traceback", done.stderr)


class RealPipelineTests(unittest.TestCase):
    """The real data/raw.csv, exported to a temporary folder and read back."""

    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.out = Path(temp.name)
        cls.raw = dp.load_data()
        cls.summary = dp.export_results(output_dir=cls.out)
        cls.clean = dp.load_export(cls.out / dp.CLEANED_FILE)
        cls.audit = dp.load_export(cls.out / dp.AUDIT_FILE)

    def test_summary_names_the_exact_source_file(self):
        digest = hashlib.sha256(dp.DEFAULT_CSV_PATH.read_bytes()).hexdigest()
        self.assertEqual(self.summary.iloc[0].tolist(),
                         ["source", "raw_file", "sha256", digest, ""])

    def test_project_outputs_are_identical_to_a_fresh_run(self):
        for name in (dp.CLEANED_FILE, dp.AUDIT_FILE, dp.SUMMARY_FILE):
            with self.subTest(name):
                path = dp.DEFAULT_OUTPUT_DIR / name
                if not path.exists():
                    self.skipTest("run data_preparation.py --clean first")
                self.assertEqual(path.read_bytes(), (self.out / name).read_bytes())

    def test_row_counts_and_raw_text_survive_the_export(self):
        self.assertEqual((len(self.audit), len(self.clean)), (930, 915))
        raw_columns = self.raw.columns.tolist()
        self.assertEqual(self.audit[raw_columns].values.tolist(),
                         self.raw.values.tolist())
        kept = self.raw.drop_duplicates()
        self.assertEqual(self.clean[raw_columns].values.tolist(), kept.values.tolist())
        self.assertEqual(self.clean["source_row"].tolist(), (kept.index + 1).tolist())
        repeats = self.audit.dropna(subset="duplicate_of_source_row")
        self.assertEqual(len(repeats), 15)
        for _, row in repeats.iterrows():
            first = self.audit.iloc[row["duplicate_of_source_row"] - 1]
            self.assertEqual(row[raw_columns].tolist(), first[raw_columns].tolist())
            self.assertNotEqual(first["row_status"], "excluded_duplicate")

    def test_numbers_match_an_independent_reading_of_the_raw_text(self):
        for field, (column, before, after) in dp.NUMERIC_FIELDS.items():
            for number, text in zip(self.clean[field], self.clean[column]):
                if pd.notna(number):
                    plain = text.removeprefix(before).removesuffix(after)
                    self.assertEqual(number, float(plain.replace(",", "")))
                    self.assertGreater(number, 0)
        known = self.clean.dropna(subset=["price_usd", "ram_gb"])
        self.assertEqual(known["price_per_gb_ram"].tolist(),
                         (known["price_usd"] / known["ram_gb"]).tolist())
        self.assertEqual(self.clean["price_per_gb_ram"].notna().sum(), len(known))

    def test_exactly_the_unclear_values_are_missing(self):
        missing = {}
        for field, (column, _, _) in dp.NUMERIC_FIELDS.items():
            missing[field] = sorted(self.clean.loc[self.clean[field].isna(), column])
        self.assertEqual(missing, {
            "price_usd": ["USD 396,22"], "launch_year": [],
            "ram_gb": ["8GB / 12GB", "8GB / 12GB"], "battery_mah": [],
            "screen_size_in": [
                "6.7 inches (internal), 3.6 inches (external)",
                "6.7 inches (main), 2.7 inches (external)",
                "6.7 inches (main), 2.7 inches (external)",
                "6.9 inches (internal), 4.0 inches (external)",
                "6.9 inches (unfolded)", "7.8 inches (unfolded)",
                "7.85 inches (unfolded)", "8.0 inches (unfolded)"],
            "weight_g": []})

    def test_brands_and_source_caveats(self):
        self.assertEqual(self.clean["brand"].nunique(), 18)
        self.assertEqual((self.clean["brand"] == "POCO").sum(), 32)
        disputed = self.clean["quality_flags"].str.contains("iphone16_specs_disputed")
        self.assertEqual(self.clean.loc[disputed, "source_row"].tolist(), [1, 2, 3])
        self.assertEqual(self.clean.loc[disputed, "weight_g"].tolist(), [174.0] * 3)
        tablets = self.audit["quality_flags"].str.contains("tablet_like_name")
        self.assertEqual(tablets.sum(), 94)


class RealLicenseTests(unittest.TestCase):
    def test_license_text_is_the_canonical_apache_file(self):
        # SHA-256 of https://www.apache.org/licenses/LICENSE-2.0.txt
        path = PROJECT_ROOT / "data" / "LICENSE-APACHE-2.0.txt"
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(),
            "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30")


if __name__ == "__main__":
    unittest.main()
