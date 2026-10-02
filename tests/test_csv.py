import pytest
from cytellect_analysis.contracts import StatisticsRequest
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
