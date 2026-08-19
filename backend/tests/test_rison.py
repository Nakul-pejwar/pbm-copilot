import re

from app.superset_client import FILTER_ID, _rison_encode


def test_rison_encode_scalars():
    assert _rison_encode(None) == "null"
    assert _rison_encode(True) == "!t"
    assert _rison_encode(False) == "!f"
    assert _rison_encode(42) == "42"
    assert _rison_encode(1.5) == "1.5"
    assert _rison_encode("TEST19") == "'TEST19'"
    assert _rison_encode("a'b!c") == "'a!'b!!c'"


def test_rison_encode_arrays_and_maps():
    assert _rison_encode(["TEST19"]) == "!('TEST19')"
    assert _rison_encode(["A", "B"]) == "!('A','B')"
    assert _rison_encode({"key with space": 1}) == "('key with space':1)"


def test_rison_encode_data_mask_payload():
    payload = {
        FILTER_ID: {
            "id": FILTER_ID,
            "filterState": {"value": ["TEST19"]},
            "extraFormData": {
                "filters": [{"col": "company_id", "op": "IN", "val": ["TEST19"]}]
            },
        }
    }
    encoded = _rison_encode(payload)
    assert encoded == (
        f"({FILTER_ID}:("
        "id:'NATIVE_FILTER-c0ffee00-0000-4000-8000-000000000001',"
        "filterState:(value:!('TEST19')),"
        "extraFormData:(filters:!((col:'company_id',op:'IN',val:!('TEST19'))))))"
    )
    assert re.fullmatch(
        r"\(NATIVE_FILTER-[\w\-]+:\(id:'NATIVE_FILTER-[\w\-]+',"
        r"filterState:\(value:!\('[\w]+'\)\),"
        r"extraFormData:\(filters:!\(\(col:'company_id',op:'IN',val:!\('[\w]+'\)\)\)\)\)\)",
        encoded,
    )