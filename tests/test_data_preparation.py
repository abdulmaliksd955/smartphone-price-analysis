"""Tests for data_preparation.py (part 1: loading and initial inspection).

Two kinds of data are used:
- RealDataTests reads the real file data/raw.csv.
- Every other class uses SYNTHETIC rows invented only for testing. They are
  written to a temporary folder and are not findings about real phones.
"""

import csv
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data_preparation import (  # noqa: E402
    DEFAULT_CSV_PATH,
    FILE_ENCODING,
    REQUIRED_COLUMNS,
    find_label_variants,
    inspect_data,
    load_data,
)

RAW_SHA256 = "bb47c4ec3d5de5c9e2d474f12edea8dfdb07fba72c94e99693d31087b103700f"


class RealDataTests(unittest.TestCase):
    def test_default_file_is_the_original_download(self):
        digest = hashlib.sha256(DEFAULT_CSV_PATH.read_bytes()).hexdigest()
        self.assertEqual(digest, RAW_SHA256)

    def test_every_raw_cell_is_preserved(self):
        with open(DEFAULT_CSV_PATH, encoding=FILE_ENCODING, newline="") as file:
            header, *rows = csv.reader(file)
        data = load_data()
        self.assertEqual(data.shape, (930, 15))
        self.assertEqual(data.columns.tolist(), header)
        self.assertEqual(data.values.tolist(), rows)

    def test_non_ascii_characters_are_decoded_and_kept(self):
        china = load_data()["Launched Price (China)"].tolist()
        self.assertIn("¥13,999", china)      # yen/yuan sign
        self.assertIn("CNY 17,999 ", china)  # trailing no-break space

    def test_inspection_matches_the_real_file(self):
        result = inspect_data(load_data())
        self.assertEqual(result["shape"], (930, 15))
        self.assertEqual(sum(result["missing_counts"].values()), 0)
        self.assertEqual(result["duplicate_rows"], 15)
        self.assertEqual(result["not_available_counts"],
                         {"Launched Price (Pakistan)": 1})
        self.assertEqual(len(result["brand_labels"]), 19)
        self.assertEqual(result["brand_variants"], {"poco": ["POCO", "Poco"]})

    def test_demo_runs_from_another_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            done = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "data_preparation.py")],
                cwd=folder, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("930 rows x 15 columns", done.stdout)


class SyntheticFileTestCase(unittest.TestCase):
    """Helper: write SYNTHETIC test-only CSV bytes to a temporary folder."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.header = ",".join(REQUIRED_COLUMNS)
        self.row = ",".join(["test"] * len(REQUIRED_COLUMNS))

    def write(self, content):
        path = self.folder / "synthetic.csv"
        path.write_bytes(content.encode("ascii")
                         if isinstance(content, str) else content)
        return path


class LoadErrorTests(SyntheticFileTestCase):
    def test_missing_file_names_the_path(self):
        with self.assertRaisesRegex(FileNotFoundError, "no_such_file.csv"):
            load_data(self.folder / "no_such_file.csv")

    def test_folder_is_not_accepted_as_a_file(self):
        with self.assertRaises(FileNotFoundError):
            load_data(self.folder)

    def test_missing_columns_are_all_named(self):
        kept = [c for c in REQUIRED_COLUMNS if c not in ("RAM", "Screen Size")]
        path = self.write(",".join(kept) + "\n" + ",".join("x" for _ in kept) + "\n")
        with self.assertRaises(ValueError) as caught:
            load_data(path)
        self.assertIn("RAM", str(caught.exception))
        self.assertIn("Screen Size", str(caught.exception))
        self.assertNotIn("Model Name", str(caught.exception))

    def test_duplicate_column_names(self):
        path = self.write(f"{self.header},RAM\n{self.row},extra\n")
        with self.assertRaisesRegex(ValueError, "(?i)duplicate column"):
            load_data(path)

    def test_empty_files(self):
        for content in ("", " \n\n"):
            with self.subTest(content=content):
                with self.assertRaisesRegex(ValueError, "(?i)empty"):
                    load_data(self.write(content))

    def test_header_without_rows(self):
        with self.assertRaisesRegex(ValueError, "(?i)no data rows"):
            load_data(self.write(self.header + "\n"))

    def test_malformed_rows_are_never_skipped_or_padded(self):
        short_row = self.row.rsplit(",", 1)[0]
        bad_rows = {"too many": self.row + ",extra", "too few": short_row,
                    "blank line": ""}
        for name, bad_row in bad_rows.items():
            with self.subTest(name):
                path = self.write(f"{self.header}\n{self.row}\n{bad_row}\n{self.row}\n")
                with self.assertRaisesRegex(ValueError, "(?i)malformed.*line 3"):
                    load_data(path)

    def test_every_row_too_long(self):
        # pandas would otherwise silently turn the first field into an index.
        path = self.write(f"{self.header}\n{self.row},extra\n{self.row},extra\n")
        with self.assertRaisesRegex(ValueError, "(?i)malformed"):
            load_data(path)

    def test_unclosed_quote(self):
        path = self.write(f'{self.header}\n"{self.row}\n{self.row}\n')
        with self.assertRaisesRegex(ValueError, "(?i)malformed"):
            load_data(path)

    def test_byte_not_valid_in_the_documented_encoding(self):
        # 0x81 has no meaning in Windows-1252.
        path = self.write(f"{self.header}\n{self.row}".encode() + b"\x81\n")
        with self.assertRaisesRegex(ValueError, FILE_ENCODING):
            load_data(path)

    def test_command_line_reports_errors_without_traceback(self):
        done = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "data_preparation.py"),
             os.fspath(self.folder / "absent.csv")],
            capture_output=True, text=True)
        self.assertEqual(done.returncode, 1)
        self.assertIn("absent.csv", done.stderr)
        self.assertNotIn("Traceback", done.stderr)


class RawValueTests(SyntheticFileTestCase):
    def test_text_is_not_converted_and_only_blank_cells_are_missing(self):
        cells = ["007", "NA", "None", " 6GB ", "", "1.50", '"USD 1,099"', "2024"]
        self.assertEqual(len(cells), len(REQUIRED_COLUMNS))
        data = load_data(self.write(f"{self.header}\n{','.join(cells)}\n"))
        values = data.iloc[0].tolist()
        self.assertTrue(pd.isna(values[4]))
        del values[4]
        self.assertEqual(values, ["007", "NA", "None", " 6GB ", "1.50",
                                  "USD 1,099", "2024"])

    def test_extra_columns_and_duplicate_rows_are_kept(self):
        row = self.row + ",note"
        data = load_data(self.write(f"{self.header},Extra\n{row}\n{row}\n"))
        self.assertEqual(data.shape, (2, len(REQUIRED_COLUMNS) + 1))
        self.assertEqual(data["Extra"].tolist(), ["note", "note"])


class InspectionTests(unittest.TestCase):
    """SYNTHETIC in-memory data only."""

    def setUp(self):
        self.data = pd.DataFrame({
            "Company Name": ["TestCo", "TESTCO", "TestCo ", "Other", "Other"],
            "RAM": ["1GB", None, "Not available", "2GB", "2GB"],
        })

    def test_reports_structure_missing_and_duplicates(self):
        result = inspect_data(self.data)
        self.assertEqual(result["shape"], (5, 2))
        self.assertEqual(result["columns"], ["Company Name", "RAM"])
        self.assertEqual(set(result["dtypes"]), {"Company Name", "RAM"})
        self.assertEqual(result["missing_counts"], {"Company Name": 0, "RAM": 1})
        self.assertEqual(result["not_available_counts"], {"RAM": 1})
        self.assertEqual(result["duplicate_rows"], 1)
        self.assertEqual(result["brand_variants"],
                         {"testco": ["TESTCO", "TestCo", "TestCo "]})

    def test_inspection_does_not_change_the_data(self):
        before = self.data.copy(deep=True)
        inspect_data(self.data)
        pd.testing.assert_frame_equal(self.data, before)

    def test_variants_cover_case_spaces_and_punctuation(self):
        labels = ["Test Co", "test-co", "TestCo", "Other", None]
        self.assertEqual(find_label_variants(labels),
                         {"testco": ["Test Co", "TestCo", "test-co"]})

    def test_no_variants_are_invented(self):
        self.assertEqual(find_label_variants(["Alpha", "Beta", "Beta"]), {})


if __name__ == "__main__":
    unittest.main()
