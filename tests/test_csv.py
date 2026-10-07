import pytest
from cytellect_analysis.contracts import StatisticsRequest
from cytellect_analysis.descriptive import describe_numeric
from cytellect_analysis.descriptive_contracts import parse_descriptive_request
from cytellect_analysis.numerical_csv import analyze_numeric, parse_numeric_csv

HEADER = "condition,experimental_unit,sample,field_id,acquisition_date,value,unit,assay\n"


def content():
    return (HEADER + "\n".join(f"{group},{group}{i},{group}{i},{group}{i},date,{i+offset},ng,RNA"
                               for group, offset in (("A", 1), ("B", 3)) for i in range(3))).encode()


def test_numeric_import_analysis_distinguishes_observations_from_cells():
    parsed = parse_numeric_csv(content())
    assert parsed["metadata"]["unit"] == "ng"
    spec = StatisticsRequest(metric="value", baseline="A", comparisons=[("A", "B")],
                             independent_units_confirmed=True)
    result = analyze_numeric(parsed["rows"], spec)
    assert result["counts"][0]["observations"] == 3
    assert "cells" not in result["counts"][0]
    assert result["comparisons"][0]["estimate"] == -2


@pytest.mark.parametrize("body", [
    b"condition,value\nA,1\n",
    (HEADER + "A,a,s,f,d,nan,ng,RNA").encode(),
    (HEADER + "A,a,s,f,d,1,ng,RNA\nA,a,s,f,d,2,ug,RNA").encode(),
    (HEADER + "A,a,s,f,d,1,ng,RNA\nB,b,s,f,d,2,ng,RNA").encode(),
    (HEADER + "A,a,s,f,d,1,ng,RNA,extra").encode(),
])
def test_reject_invalid_csv(body):
    with pytest.raises(ValueError):
        parse_numeric_csv(body)


def test_no_implicit_gfp_model_for_numeric_assay():
    rows = parse_numeric_csv(content())["rows"]
    request = StatisticsRequest(metric="value", mode="exploratory", baseline="A", comparisons=[("A", "B")])
    with pytest.raises(ValueError, match="numeric_assay_requires"):
        analyze_numeric(rows, request)


def test_native_region_sensitivity_cannot_be_attached_to_numeric_table():
    rows = parse_numeric_csv(content())["rows"]
    request = StatisticsRequest(metric="value", baseline="A", comparisons=[("A", "B")],
                                independent_units_confirmed=True, sensitivity_region_revision_ids=["alternate"])
    with pytest.raises(ValueError, match="image_sensitivities_not_applicable"):
        analyze_numeric(rows, request)


def test_explicit_descriptive_import_preserves_unknown_study_metadata():
    raw = b"field_id,value,unit\nfield-a,-2,ng\nfield-a,0,ng\nfield-b,4,ng\n"
    with pytest.raises(ValueError, match="numeric_csv_columns_invalid"):
        parse_numeric_csv(raw)
    parsed = parse_numeric_csv(raw, mode="descriptive")
    assert parsed["metadata"]["conditions"] == []
    assert parsed["metadata"]["import_mode"] == "descriptive"
    assert all(row[key] is None for row in parsed["rows"]
               for key in ("condition", "sample", "experimental_unit", "acquisition_date", "pair"))
    spec = parse_descriptive_request({"mode": "descriptive", "selection": {"source": "numerical"}})
    result = describe_numeric(parsed["rows"], spec)
    assert result["counts"]["observations"] == 3
    assert result["counts"]["experimental_units"] is None
    assert result["field_summary"][0]["median"] == -1
    assert result["field_summary"][1]["median"] == 4
    with pytest.raises(ValueError, match="numeric_csv_metadata_invalid"):
        analyze_numeric(parsed["rows"], specification_for_missing_metadata())


def specification_for_missing_metadata():
    return StatisticsRequest(metric="value", baseline="A", comparisons=[("A", "B")],
                             independent_units_confirmed=True)


@pytest.mark.parametrize("raw", [b"field_id,value\n,1\n", b"field_id,value\nf,nan\n",
                                     b"field_id,value\nf,1,extra\n",
                                     b"field_id,value,condition\nf,1,A\nf,2,B\n"])
def test_descriptive_import_keeps_source_validation(raw):
    with pytest.raises(ValueError):
        parse_numeric_csv(raw, mode="descriptive")
