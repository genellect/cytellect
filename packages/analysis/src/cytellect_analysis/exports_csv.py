"""Portable CSV exports with spreadsheet formula interpretation disabled for strings."""
import csv
from pathlib import Path


def write_csv(path: Path, rows):
    columns = list(dict.fromkeys(key for row in rows for key in row))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            safe = {}
            for key, value in row.items():
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                    value = "'" + value
                safe[key] = value
            writer.writerow(safe)
