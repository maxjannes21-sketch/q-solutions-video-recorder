import csv
import sys
from pathlib import Path

import qscript


INPUT_FILE = Path("input.csv")
COLUMNS = [
    "URL",
    "Company Name",
    "Language",
    "Country",
    "Postcode",
    "City",
    "Street",
    "HouseNo",
]


def main():
    if not INPUT_FILE.is_file():
        print("Input file not found: " + str(INPUT_FILE.resolve()), file=sys.stderr)
        return 2

    qscript.PATH_TO_VIDEO_FOLDER = str(Path("./video").resolve())
    succeeded = 0
    failed = 0

    try:
        with INPUT_FILE.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, delimiter=";", quotechar='"')
            if reader.fieldnames != COLUMNS:
                raise ValueError(
                    "Unexpected CSV header. Expected: " + ";".join(COLUMNS)
                )

            for row_number, row in enumerate(reader, start=2):
                values = {
                    column: (row.get(column) or "").strip() for column in COLUMNS
                }
                print(
                    "Processing row " + str(row_number) + ": " + values["Company Name"],
                    flush=True,
                )
                video_path = qscript.CaptureVideo_Magento(
                    values["URL"],
                    values["Company Name"],
                    values["Language"],
                    values["Country"],
                    values["Postcode"],
                    values["City"],
                    values["Street"],
                    values["HouseNo"],
                )
                if video_path is None:
                    failed += 1
                    print("Row " + str(row_number) + " failed", file=sys.stderr)
                else:
                    succeeded += 1
                    print(video_path, flush=True)
    except (OSError, csv.Error, ValueError) as error:
        print("Could not process CSV: " + str(error), file=sys.stderr)
        return 2

    print("Completed: " + str(succeeded) + " saved, " + str(failed) + " failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())