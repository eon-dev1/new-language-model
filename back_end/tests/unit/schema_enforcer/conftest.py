"""
Shared fixtures for schema_enforcer tests.

Provides mock MongoDB connector with configurable responses
for testing the SchemaEnforcer without a real database.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class AsyncIterator:
    """Helper to mock async iteration (for cursor.aggregate)"""

    def __init__(self, items):
        self.items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.items)
        except StopIteration:
            raise StopAsyncIteration


@pytest.fixture
def mock_db():
    """
    Mock MongoDBConnector with cached collection mocks.

    Mirrors the real MongoDBConnector interface:
    - get_database() -> sync, returns database object
    - get_collection(name) -> sync, returns collection object
    - Collection methods like list_collection_names(), index_information() -> async

    Critical: Uses caching to ensure the same collection mock is returned
    when get_collection is called multiple times with the same name.
    """
    db = MagicMock()  # MongoDBConnector is sync (methods return async objects)

    # Database mock with async list_collection_names
    database_mock = MagicMock()
    database_mock.list_collection_names = AsyncMock(
        return_value=[
            "languages",
            "bible_books",
            "bible_texts",
            "base_structure_bible",
            "dictionaries",
            "grammar_systems",
        ]
    )
    db.get_database = MagicMock(return_value=database_mock)

    # Cache collection mocks to ensure same instance returned
    _collection_cache = {}

    def make_collection_mock(name):
        coll = MagicMock()
        coll.index_information = AsyncMock(
            return_value={"_id_": {"key": [("_id", 1)]}}
        )
        coll.count_documents = AsyncMock(return_value=0)
        coll.aggregate = MagicMock(return_value=AsyncIterator([]))
        coll.create_index = AsyncMock(return_value="new_index")
        # For seed data checking/insertion
        coll.find_one = AsyncMock(return_value=None)  # Assume doc doesn't exist
        coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id="test_id"))
        return coll

    def get_or_create_collection(name):
        if name not in _collection_cache:
            _collection_cache[name] = make_collection_mock(name)
        return _collection_cache[name]

    db.get_collection = MagicMock(side_effect=get_or_create_collection)
    db._collection_cache = _collection_cache  # Expose for test assertions

    return db
