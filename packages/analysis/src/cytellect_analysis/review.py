"""Scientific review gates shared by API, workers, and export replay."""


def unresolved_nucleolar_failures(report, config):
    """Only explicit, reasoned configuration exclusions clear failed nuclei.

    A review checkbox accepting invalidated masks and a mutable row's excluded
    flag are not evidence that a failed candidate operation was acknowledged.
    """
    exclusions = {(row["field_id"], row.get("nucleus_id")) for row in config.get("exclusions", [])
                  if isinstance(row.get("reason"), str) and row["reason"].strip()}
    failed = {(row["field_id"], int(row["nucleus_id"])) for row in report.get("cells", [])
              if row.get("nucleolar_status") == "processing_failed"}
    failed.update((row["field_id"], int(row["nucleus_id"])) for row in report.get("nucleolar_failures", []))
    return [{"field_id": field, "nucleus_id": nucleus} for field, nucleus in sorted(failed)
            if (field, nucleus) not in exclusions and (field, None) not in exclusions]
