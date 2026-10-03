"""Portable CSV exports with spreadsheet formula interpretation disabled for strings."""
import csv
import hashlib
from pathlib import Path


def write_csv(path: Path, rows, *, columns=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        _write_rows(stream, rows, columns=columns)


def _write_rows(stream, rows, *, columns=None):
    if columns is None:
        columns = list(dict.fromkeys(key for row in rows for key in row))
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        safe = {}
        for key, value in row.items():
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                value = "'" + value
            safe[key] = value
        writer.writerow(safe)


def csv_sha256(rows, *, columns=None):
    """Hash the exact UTF-8-sig CSV stream without a research-data temporary file."""
    digest = hashlib.sha256(b"\xef\xbb\xbf")

    class HashWriter:
        def write(self, text):
            digest.update(text.encode("utf-8"))
            return len(text)

    _write_rows(HashWriter(), rows, columns=columns)
    return digest.hexdigest()
