"""
Shared in-memory MongoDB mock for phrase_index tests.

Keeps the mocking minimal: only the operators actually used by the builder
and the get_phrase_context tool. Adding features here should be driven by a
failing test, not speculation.
"""

import re
from functools import cmp_to_key
from typing import Any


def _match_value(doc_value, query_value):
    if isinstance(query_value, dict):
        for op, op_value in query_value.items():
            if op == "$in":
                if doc_value not in op_value:
                    return False
            elif op == "$gte":
                if doc_value is None or doc_value < op_value:
                    return False
            elif op == "$lte":
                if doc_value is None or doc_value > op_value:
                    return False
            elif op == "$regex":
                flags = re.IGNORECASE if query_value.get("$options") == "i" else 0
                if not re.search(op_value, str(doc_value or ""), flags):
                    return False
            elif op == "$options":
                pass
            elif op == "$ne":
                if doc_value == op_value:
                    return False
            else:
                # Unknown — permissive skip
                pass
        return True
    return doc_value == query_value


def _matches(doc, query):
    for k, v in query.items():
        if k == "$or":
            if not any(_matches(doc, clause) for clause in v):
                return False
        elif k == "$and":
            if not all(_matches(doc, clause) for clause in v):
                return False
        else:
            if not _match_value(doc.get(k), v):
                return False
    return True


class _Cursor:
    def __init__(self, docs):
        self._docs = list(docs)
        self._sort = None

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, str):
            spec = [(key_or_list, direction or 1)]
        else:
            spec = list(key_or_list)

        def cmp(a, b):
            for field, d in spec:
                av, bv = a.get(field), b.get(field)
                if av == bv:
                    continue
                if av is None:
                    return d
                if bv is None:
                    return -d
                if av < bv:
                    return -d
                return d
            return 0

        self._docs = sorted(self._docs, key=cmp_to_key(cmp))
        return self

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class MockCollection:
    def __init__(self, docs: list[dict[str, Any]] | None = None):
        self.docs: list[dict[str, Any]] = list(docs or [])
        self.insert_many_calls: list[list[dict[str, Any]]] = []
        self.delete_many_calls: list[dict[str, Any]] = []

    async def find_one(self, query):
        for d in self.docs:
            if _matches(d, query):
                return d
        return None

    def find(self, query=None, projection=None):
        query = query or {}
        matched = [d for d in self.docs if _matches(d, query)]
        return _Cursor(matched)

    async def delete_many(self, query):
        self.delete_many_calls.append(dict(query))
        remaining = [d for d in self.docs if not _matches(d, query)]
        deleted = len(self.docs) - len(remaining)
        self.docs = remaining
        return type("R", (), {"deleted_count": deleted})()

    async def insert_many(self, docs):
        docs = list(docs)
        if not docs:
            # Real motor raises on []. The builder MUST guard before calling.
            raise ValueError("insert_many called with empty list")
        self.insert_many_calls.append(docs)
        self.docs.extend(docs)
        return type("R", (), {"inserted_ids": [d.get("_id", i) for i, d in enumerate(docs)]})()


class MockDB:
    def __init__(self):
        self.collections: dict[str, MockCollection] = {}

    def get_collection(self, name):
        # Support Enum or string
        key = name.value if hasattr(name, "value") else name
        if key not in self.collections:
            self.collections[key] = MockCollection()
        return self.collections[key]

    def seed(self, name, docs):
        key = name.value if hasattr(name, "value") else name
        self.collections[key] = MockCollection(docs)
