# Dataset and cleaning

## Source and identity

| Item | Value |
| --- | --- |
| Dataset | [Mobiles Dataset (2025)](https://www.kaggle.com/datasets/abdulmalik1518/mobiles-dataset-2025), Kaggle Version 1 |
| Publisher | Abdul Malik (Kaggle user `abdulmalik1518`) |
| License | Apache 2.0, as listed on the Kaggle page; full text in `data/LICENSE-APACHE-2.0.txt` |
| Accessed / downloaded | 2026-11-25 (UTC), through the public Kaggle page in a browser, without login |
| Download link | <https://www.kaggle.com/api/v1/datasets/download/abdulmalik1518/mobiles-dataset-2025?datasetVersionNumber=1> (direct server requests returned 404; the browser download worked) |
| Original file name | `Mobiles Dataset (2025).csv`, stored unedited as `data/raw.csv` |
| Size | 140,323 bytes; 930 data rows, 15 columns |
| SHA-256 | `bb47c4ec3d5de5c9e2d474f12edea8dfdb07fba72c94e99693d31087b103700f` |
| Encoding | Windows-1252 (`cp1252`), CRLF line endings |

Source, license and download facts were recorded when the file was obtained.
Size, hash, shape and encoding were checked on the local file.

**Why Windows-1252?** The file is not valid UTF-8. It has exactly two non-ASCII
bytes: `0xA5` (`¥` in `¥13,999`) and `0xA0` (a no-break space after
`CNY 17,999`), both in the China price column. Latin-1 gives the same text for
these bytes; we use `cp1252` because it rejects some undefined bytes instead of
accepting everything. This cannot detect every wrongly encoded file.

## Attribution and license

The dataset is by Abdul Malik (source link above), shown under the Apache License 2.0.
`data/LICENSE-APACHE-2.0.txt` is copied from the canonical
<https://www.apache.org/licenses/LICENSE-2.0.txt>.

**Modification notice:** `data/raw.csv` is unmodified (only renamed). The files in
`outputs/` are modified by this project: repeated rows are marked or removed, and
cleaned columns, flags and row numbers are added. Any shared copy of these files must
include this notice ([data/ATTRIBUTION.md](../data/ATTRIBUTION.md)) and the license text. Nothing has been published by this work.
This license covers the dataset; it does not license the project's own code.

## Data dictionary

All values are loaded as **text**, exactly as written. Columns marked * are in
`REQUIRED_COLUMNS`; the others are kept but not needed for the main questions.

| Raw column | Meaning | Example |
| --- | --- | --- |
| `Company Name` * | Brand label | `Apple` |
| `Model Name` * | Model, often with storage size | `iPhone 16 128GB` |
| `Mobile Weight` * | Weight in grams | `174g` |
| `RAM` * | Memory; some rows list two sizes | `6GB`, `8GB / 12GB` |
| `Front Camera` | Front camera resolution | `12MP` |
| `Back Camera` | Back camera resolution(s) | `48MP` |
| `Processor` | Chip name | `A17 Bionic` |
| `Battery Capacity` * | Battery capacity; comma is optional | `3,600mAh` |
| `Screen Size` * | Diagonal in inches; foldables may list two | `6.1 inches` |
| `Launched Price (Pakistan)` | Launch price, PKR | `PKR 224,999` |
| `Launched Price (India)` | Launch price, INR | `INR 79,999` |
| `Launched Price (China)` | Launch price, CNY | `CNY 5,799` |
| `Launched Price (USA)` * | Historical USA launch price, USD | `USD 799` |
| `Launched Price (Dubai)` | Launch price, AED | `AED 2,799` |
| `Launched Year` * | Launch year | `2024` |

## Raw inspection (`python data_preparation.py`)

- 930 rows, 15 columns, all text; 0 empty cells.
- "0 empty" does not mean "all known": one Pakistan price is the text
  `Not available`.
- 15 exact duplicate rows (repeats after the first copy). They stay in the raw data.
- 19 raw brand labels. The set check found one variant pair: `POCO` (30 rows) and
  `Poco` (2 rows). Reading the sorted labels showed no other misspelling.

## Source-quality concerns (documented, not fixed)

- **Specifications may be wrong.** The first record, iPhone 16 128GB, lists A17
  Bionic and 174g. [Apple's official page](https://support.apple.com/en-us/121029)
  lists A18 and 170g.
- **Not only smartphones.** Tablets are included: 17 model names contain `iPad`,
  and 94 contain `Pad` or `Tab` (including those 17; a simple text match).
- **Ambiguous price.** Nokia T21 has the USA price `USD 396,22`.
- **Mixed formats.** There are entries such as `8GB / 12GB`, two-screen foldables,
  and USD prices with decimals.

Successful loading only shows that the file is readable and regular. It does not
show that its facts are correct, and these counts are not final research results.

## Report draft: dataset description

We use Version 1 of the public "Mobiles Dataset (2025)" from Kaggle, published by
Abdul Malik under the Apache 2.0 license and accessed on 25 November 2026. The raw
file has 930 records and 15 attributes covering brand, model, weight, memory,
cameras, processor, battery, screen size, launch year (2014–2025), and launch
prices in five markets. Each record is a listed model or storage variant, so one
model can appear in several rows.

Our question is how specifications, mainly RAM, and brand are associated with the
USA launch price in US dollars. Launch prices are historical: they are not current
retail prices, are not adjusted for inflation, and come from different years. The
data is observational, so a relationship between RAM and price would be an
association and would not prove that RAM causes a higher price. Brand, launch year,
storage, and other specifications may also explain price differences.

The source has limits. It is a community dataset, it includes tablets, and at least
one record disagrees with the manufacturer's specifications (iPhone 16: processor
and weight). It may not represent every phone sold in the USA. We therefore treat
its values as reported by the source, not as independently verified facts.

## Cleaning policy (`clean_data()`)

One clear number with the documented unit is converted. Anything else becomes
missing with a reason in `quality_flags`; nothing is guessed or replaced by zero.

| Reason | Meaning | Real cases |
| --- | --- | --- |
| `missing`, `placeholder` | Empty cell, or text such as `Not available` | 0 in the cleaned columns |
| `ambiguous_separator` | Comma or dot readable in two ways | Nokia T21 `USD 396,22` |
| `multiple_values` | Two or more numbers | 2 RAM (`8GB / 12GB`), 4 two-screen phones |
| `qualified_value` | A number with a note in brackets | 4 screens such as `8.0 inches (unfolded)` |
| `not_positive`, `out_of_range`, `unexpected_format` | Zero/negative; year outside 1983–2026 or an impossibly long number; wrong unit or currency | none |

- `price_per_gb_ram` is missing when price or RAM is missing. RAM is always positive, so
  there is no division by zero. If the division is too large for a number (infinity),
  the ratio is missing and flagged `price_per_gb_ram:not_finite`; the price and RAM are
  kept. No real row has this case.
- Commas are accepted only as thousands separators, and only in price and battery.
  Three digits after a dot (`5.000mAh`) are ambiguous. Decimals are preserved.
- `qualified_value` is a cautious choice: `(unfolded)` sizes are left missing because
  the note shows the size is not simply "the screen". The raw text is still there.
- Brand: `Poco` becomes `POCO` (the set check found no other pair); extra spaces are
  tidied. Both `Poco` rows are POCO Pad tablets.
- Only rows identical in **all** raw columns are repeats. The first is kept. Storage
  variants, and rows that become alike only after cleaning, are kept.
- Other currencies are not converted. Cameras and processor remain raw text, because
  several cameras are not one safe number.
- Review flags that change nothing: `model:tablet_like_name` (name contains `Pad` or
  `Tab`) and `source:iphone16_specs_disputed` (iPhone 16 rows with 174g).

## Cleaned schema (`outputs/cleaned_mobiles.csv`)

| Column | Type | Unit / meaning |
| --- | --- | --- |
| `source_row` | integer | Position in `raw.csv`, first data row = 1 |
| `row_status` | text | `retained` or `retained_flagged` (has a quality flag) |
| `brand`, `model` | text | Tidied labels |
| `price_usd` | decimal | Historical USA launch price, USD |
| `launch_year` | integer | Year |
| `ram_gb` | decimal | GB |
| `battery_mah` | decimal | mAh |
| `screen_size_in` | decimal | Diagonal, inches |
| `weight_g` | decimal | Grams |
| `price_per_gb_ram` | decimal | `price_usd / ram_gb`, USD per GB |
| `quality_flags` | text | `column:reason`, separated by `;`; empty if none |
| `format_fixes` | text | Harmless notation changes, e.g. `price_usd:comma_removed` |
| 15 raw columns | text | Unchanged, original names |

`row_audit.csv` has all 930 rows with the same columns. Its first column is
`duplicate_of_source_row`, and repeats have the status `excluded_duplicate`.
`cleaning_summary.csv` has `section, field, measure, value, unit`.
Unit text is removed from every converted number, so that is not listed as a fix.
`price_per_gb_ram` is descriptive only: it is not a value-for-money score, and the
whole price is not caused by RAM.

**Reading the data.** `load_export(path)` returns the documented types. To leave out
tablet-like names: `data[~data["quality_flags"].str.contains("tablet_like_name")]`.
This does not give a verified phone-only sample (for
example, the 10.4-inch Nokia T21 is not caught).

**Managed outputs.** `--clean` writes only the three files above (UTF-8). It replaces
them only if their header shows an earlier export; otherwise it stops before writing
anything. Edits made inside these three files are lost on the next run. Links, and
folders that hold the raw data, are refused. The same input gives identical bytes.

## Cleaning results (actual run on the real file)

| Check | Before | After |
| --- | --- | --- |
| Rows | 930 | 915 (15 exact repeats excluded: 14 Oppo, 1 Infinix) |
| Status | – | 807 retained, 108 retained and flagged |
| Brand labels | 19 | 18 |
| Missing price / RAM / screen size | 0 / 0 / 0 blank | 1 / 2 / 8 |
| Missing year, battery, weight, brand, model | 0 | 0 |
| Missing `price_per_gb_ram` | – | 3 |

Missing counts rise because unclear text is now visibly missing. Flags in the 915
rows: 94 tablet-like names, 8 screen sizes, 3 disputed iPhone 16 rows, 2 RAM, 1 price.
Formatting fixes: 601 battery commas, 137 price commas, 2 brand labels.

| Column | Minimum | Maximum |
| --- | --- | --- |
| `price_usd` | 79 | 2799 |
| `launch_year` | 2014 | 2025 |
| `ram_gb` | 1 | 16 |
| `battery_mah` | 2000 | 11200 |
| `screen_size_in` | 5.0 | 14.6 |
| `weight_g` | 135 | 732 |
| `price_per_gb_ram` | 19.08 | 366.33 (rounded here only) |

Ranges include tablet-like devices and only check the cleaning.

## Report draft: data cleaning

The raw file was kept unchanged and all cleaning was done on a copy with Pandas. We
first checked that every required column existed. We then removed the units from USA
launch price, RAM, battery capacity, screen size and weight, and converted these
columns and the launch year to numbers. Thousands commas were removed and decimals
were preserved. A set of brand labels showed one spelling difference, `POCO` and
`Poco`, which we wrote as `POCO`.

We did not guess unclear values. The price `USD 396,22` could be read in more than one
way, two records listed `8GB / 12GB`, and eight foldable screen sizes were not a single
plain value. These eleven cells became missing, and the reason was recorded. No missing
value was filled in, because an average or zero would invent data.

Fifteen rows that repeated an earlier row in all fifteen columns were excluded, leaving
915 of 930 records. Storage variants were kept because the source lists them as separate
records, often with different prices. Every record, including the excluded ones, remains in an audit file
with its original row number and original text.

We added one attribute, `price_per_gb_ram`, the USA launch price divided by RAM in GB.
It is available for 912 records. It describes the records and does not measure value or
show that RAM causes the price.

Cleaning fixed the format of the data, not its facts. Three iPhone 16 records conflict
with Apple's published weight and processor; they were flagged and not corrected. Also,
94 records have tablet-like names, and this name check is not complete. They were kept and flagged, so the cleaned
data describes mixed mobile devices rather than only smartphones.
