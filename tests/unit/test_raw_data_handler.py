from moneywiz_api.model.raw_data_handler import RawDataHandler


def test_filter_row_with_all_keys():
    row = {
        "ZMANUALHISTORICALPRICESPERSHARE": b"binary",
        "ZIMPORTLINKIDARRAY2": b"binary",
        "ZIMPORTLINKIDARRAY": b"binary",
        "ZBANKLOGOPRIMARYCOLOR": b"binary",
        "ZNAME": "Test",
        "ZAMOUNT": 100.0,
        "Z9_INTERNAL": "hidden",
        "ZNULLFIELD": None,
    }
    result = RawDataHandler.filter_row(row)
    assert "ZNAME" in result
    assert "ZAMOUNT" in result
    assert "ZMANUALHISTORICALPRICESPERSHARE" not in result
    assert "ZIMPORTLINKIDARRAY2" not in result
    assert "ZIMPORTLINKIDARRAY" not in result
    assert "ZBANKLOGOPRIMARYCOLOR" not in result
    assert "Z9_INTERNAL" not in result
    assert "ZNULLFIELD" not in result


def test_filter_row_missing_keys():
    """MoneyWiz 版本差异可能导致某些列不存在"""
    row = {
        "ZNAME": "Test",
        "ZAMOUNT": 100.0,
    }
    result = RawDataHandler.filter_row(row)
    assert result == {"ZNAME": "Test", "ZAMOUNT": 100.0}
