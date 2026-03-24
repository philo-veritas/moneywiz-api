from dataclasses import dataclass, asdict, field
from decimal import Decimal
from typing import Dict, Any
from datetime import datetime

from moneywiz_api.types import ID, ENT_ID
from moneywiz_api.model.raw_data_handler import RawDataHandler as RDH


@dataclass
class Record:
    _raw: Dict[str, Any] = field(repr=False)
    _ent: ENT_ID = field(repr=False)
    _created_at: datetime = field(repr=False)
    gid: str = field(repr=False)
    id: ID

    def __init__(self, row):
        self._raw = row
        self._ent = row["Z_ENT"]
        self._created_at = RDH.get_datetime(row, "ZOBJECTCREATIONDATE")
        self.gid = row["ZGID"]
        self.id = row["Z_PK"]

        # Fixes

        # Validate
        assert self._raw
        assert self._ent
        assert self._created_at
        assert self.gid
        assert self.id

    def ent(self) -> ENT_ID:
        return self._ent

    def filtered(self) -> Dict[str, Any]:
        """
        Utility function to return cleaned up entities.
        it will exclude fields like binary, Z9_

        :return:
        """
        return RDH.filter_row(self._raw)
        # copy = {k: v for k, v in self._raw.items()}
        # # del copy["ZGID"]
        # del copy["ZMANUALHISTORICALPRICESPERSHARE"]
        # del copy["ZIMPORTLINKIDARRAY2"]
        # del copy["ZIMPORTLINKIDARRAY"]
        # del copy["ZBANKLOGOPRIMARYCOLOR"]
        # return {
        #     k: v
        #     for k, v in copy.items()
        #     if (v is not None) and (not k.startswith("Z9_"))
        # }

    def as_dict(self) -> Dict[str, Any]:
        """返回 dataclass 实例的 dict（排除 _ 前缀的内部字段）。"""
        original = asdict(self)
        return {k: v for k, v in original.items() if not k.startswith("_")}

    def to_dict(self) -> Dict[str, Any]:
        """返回 JSON 友好的 dict（Decimal→float, datetime→ISO 字符串）。"""
        return self._convert_values(self.as_dict())

    @staticmethod
    def _convert_values(d: Dict[str, Any]) -> Dict[str, Any]:
        converted: Dict[str, Any] = {}
        for k, v in d.items():
            if isinstance(v, Decimal):
                converted[k] = float(v)
            elif isinstance(v, datetime):
                converted[k] = v.isoformat()
            elif isinstance(v, dict):
                converted[k] = Record._convert_values(v)
            elif isinstance(v, list):
                converted[k] = [Record._convert_value(item) for item in v]
            else:
                converted[k] = v
        return converted

    @staticmethod
    def _convert_value(v: Any) -> Any:
        if isinstance(v, Decimal):
            return float(v)
        elif isinstance(v, datetime):
            return v.isoformat()
        elif isinstance(v, dict):
            return Record._convert_values(v)
        elif isinstance(v, list):
            return [Record._convert_value(item) for item in v]
        return v
