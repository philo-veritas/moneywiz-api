from abc import ABC, abstractmethod
from typing import Dict, Generic, TypeVar, Callable, List, Optional

from moneywiz_api.database_accessor import DatabaseAccessor
from moneywiz_api.model.record import Record
from moneywiz_api.types import ID, GID


T = TypeVar("T", bound=Record)


class RecordManager(ABC, Generic[T]):
    def __init__(self):
        self._records: Dict[ID, T] = {}
        self._gid_to_id: Dict[GID, ID] = {}

    @property
    @abstractmethod
    def ents(self) -> Dict[str, Callable]:
        raise NotImplementedError()

    def load(self, db_accessor: DatabaseAccessor) -> None:
        records = db_accessor.query_objects(self.ents.keys())

        for record in records:
            typename = db_accessor.typename_for(record["Z_ENT"])
            if typename in self.ents:
                obj = self.ents[typename](record)
                self.add(obj)

    def add(self, record: T) -> None:
        self._records[record.id] = record
        if record.gid in self._gid_to_id:
            raise RuntimeError(
                f"Duplicate gid for {record}, existing record Id {self._gid_to_id[record.gid]}"
            )

        self._gid_to_id[record.gid] = record.id

    def get(self, record_id: ID) -> T | None:
        return self._records.get(record_id)

    def get_by_gid(self, gid: GID) -> T | None:
        return self._records.get(self._gid_to_id.get(gid))

    def get_all(self) -> List[T]:
        """返回所有记录的列表。"""
        return list(self._records.values())

    def records(self) -> Dict[ID, T]:
        return self._records

    def filter(self, predicate: Callable[[T], bool]) -> List[T]:
        """通过谓词函数过滤记录。

        示例: manager.filter(lambda r: r.name == "餐饮")
        """
        return [r for r in self._records.values() if predicate(r)]

    def find_one(self, predicate: Callable[[T], bool]) -> Optional[T]:
        """返回第一个满足条件的记录，无匹配返回 None。"""
        for r in self._records.values():
            if predicate(r):
                return r
        return None

    def count(self) -> int:
        """返回记录总数。"""
        return len(self._records)

    def __repr__(self):
        return "\n".join(f"{key}: {value}" for key, value in self.records().items())
