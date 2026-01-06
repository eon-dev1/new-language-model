"""
Shared fixtures for MCP server tests.

Provides mock MongoDB connector with test data matching schema_definition.py.
"""

import re
import pytest
from functools import cmp_to_key
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime


def _match_value(doc_value, query_value):
    """
    Match a document value against a query value, supporting MongoDB operators.

    Supports: $in, $gte, $lte, $gt, $lt, $ne, $regex (with $options)
    """
    if isinstance(query_value, dict):
        # Handle MongoDB operators
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
            elif op == "$gt":
                if doc_value is None or doc_value <= op_value:
                    return False
            elif op == "$lt":
                if doc_value is None or doc_value >= op_value:
                    return False
            elif op == "$ne":
                if doc_value == op_value:
                    return False
            elif op == "$regex":
                flags = re.IGNORECASE if query_value.get("$options") == "i" else 0
                if not re.match(op_value, str(doc_value or ""), flags):
                    return False
            elif op == "$options":
                # Skip - handled with $regex
                pass
            else:
                # Unknown operator - skip for forward compatibility
                pass
        return True
    else:
        # Simple equality
        return doc_value == query_value


def _matches_query(doc, query):
    """Check if a document matches a MongoDB query."""
    for key, value in query.items():
        doc_value = doc.get(key)
        if not _match_value(doc_value, value):
            return False
    return True


# Test data matching actual schema from schema_definition.py
TEST_LANGUAGES = [
    {
        "_id": "lang_english",
        "language_code": "english",
        "language_name": "English",
        "is_base_language": True,
        "status": "active",
        "created_at": datetime(2024, 1, 1),
        "translation_levels": {
            "human": {
                "books_started": 66,
                "books_completed": 66,
                "verses_translated": 31102,
            }
        },
        "metadata": {"creator": "system"},
    },
    {
        "_id": "lang_heb",
        "language_code": "heb",
        "language_name": "Hebrew",
        "is_base_language": False,
        "status": "active",
        "created_at": datetime(2024, 1, 1),
        "translation_levels": {
            "human": {"books_started": 5, "books_completed": 2, "verses_translated": 1500},
            "ai": {"books_started": 10, "books_completed": 0, "verses_translated": 3000},
        },
        "metadata": {"creator": "test"},
    },
    {
        "_id": "lang_bughotu",
        "language_code": "bughotu",
        "language_name": "Bughotu",
        "is_base_language": False,
        "status": "active",
        "created_at": datetime(2024, 1, 1),
        "translation_levels": {
            "human": {"books_started": 1, "books_completed": 0, "verses_translated": 2},
            "ai": {"books_started": 1, "books_completed": 0, "verses_translated": 5},
        },
        "metadata": {"creator": "test"},
    },
]

TEST_BIBLE_BOOKS = [
    {
        "_id": "book_eng_genesis",
        "language_code": "english",
        "language_name": "English",
        "book_name": "Genesis",
        "book_code": "genesis",
        "translation_type": "human",
        "total_chapters": 50,
        "total_verses": 1533,
        "chapters": [
            {"chapter": 1, "verse_count": 31},
            {"chapter": 2, "verse_count": 25},
        ],
        "created_at": datetime(2024, 1, 1),
        "translation_status": "complete",
        "metadata": {"testament": "old", "canonical_order": 1, "translator_type": "human"},
    },
    {
        "_id": "book_heb_genesis",
        "language_code": "heb",
        "language_name": "Hebrew",
        "book_name": "בראשית",
        "book_code": "genesis",
        "translation_type": "human",
        "total_chapters": 50,
        "total_verses": 1533,
        "chapters": [{"chapter": 1, "verse_count": 31}],
        "created_at": datetime(2024, 1, 1),
        "translation_status": "in_progress",
        "metadata": {"testament": "old", "canonical_order": 1, "translator_type": "human"},
    },
    {
        "_id": "book_bughotu_genesis_ai",
        "language_code": "bughotu",
        "language_name": "Bughotu",
        "book_name": "Genesis",
        "book_code": "genesis",
        "translation_type": "ai",
        "total_chapters": 50,
        "total_verses": 1533,
        "chapters": [{"chapter": 1, "verse_count": 31}],
        "created_at": datetime(2024, 1, 1),
        "translation_status": "in_progress",
        "metadata": {"testament": "old", "canonical_order": 1, "translator_type": "ai"},
    },
]

# Expanded test data for batch testing (15 verses total)
# English Genesis 1:1-10 (10 verses) + Hebrew Genesis 1:1-5 (5 verses)
_ENGLISH_GENESIS_VERSES = [
    "In the beginning God created the heavens and the earth.",
    "Now the earth was formless and empty, darkness was over the surface of the deep.",
    "And God said, Let there be light, and there was light.",
    "God saw that the light was good, and he separated the light from the darkness.",
    "God called the light day, and the darkness he called night.",
    "And God said, Let there be a vault between the waters.",
    "So God made the vault and separated the water under the vault from the water above it.",
    "God called the vault sky. And there was evening, and there was morning.",
    "And God said, Let the water under the sky be gathered to one place.",
    "God called the dry ground land, and the gathered waters he called seas.",
]

_HEBREW_GENESIS_VERSES = [
    "בראשית ברא אלהים את השמים ואת הארץ",
    "והארץ היתה תהו ובהו וחשך על פני תהום",
    "ויאמר אלהים יהי אור ויהי אור",
    "וירא אלהים את האור כי טוב",
    "ויקרא אלהים לאור יום ולחשך קרא לילה",
]

# Bughotu Genesis 1:3-7 (AI translations, with human override on verse 5)
_BUGHOTU_GENESIS_VERSES_AI = {
    3: "Na God ke taram, 'Ke rarangai ke atu mai,' ma na rarangai ke atu mai.",
    4: "Na God ke re'a na rarangai ke ke'a, ma ke tufa'i na rarangai hahoru na vunagi.",
    5: "Na God ke goroa na rarangai 'Dani,' ma na vunagi ke goroa 'Bongi.' (AI version)",
    6: "Na God ke taram, 'Ke tohu i loko na beti ke tufa'i na beti hahoru na beti.'",
    7: "Na God ke au'uta na tohu ma ke tufa'i na beti i raro na tohu.",
}

_BUGHOTU_GENESIS_VERSE_5_HUMAN = "Na God ke goroa na rarangai 'Dani,' ma na vunagi ke goroa 'Bongi.' (Human verified)"

TEST_BIBLE_TEXTS = [
    # English Genesis 1:1-10 (10 verses for batch testing)
    *[
        {
            "_id": f"verse_eng_gen_1_{i+1}",
            "language_code": "english",
            "book_code": "genesis",
            "chapter": 1,
            "verse": i + 1,
            "translation_type": "human",
            "english_text": _ENGLISH_GENESIS_VERSES[i],
            "created_at": datetime(2024, 1, 1),
        }
        for i in range(10)
    ],
    # Hebrew Genesis 1:1-5 (5 verses for batch testing)
    *[
        {
            "_id": f"verse_heb_gen_1_{i+1}",
            "language_code": "heb",
            "book_code": "genesis",
            "chapter": 1,
            "verse": i + 1,
            "translation_type": "human",
            "translated_text": _HEBREW_GENESIS_VERSES[i],
            "human_verified": i < 3,  # First 3 verified, last 2 not
            "created_at": datetime(2024, 1, 1),
        }
        for i in range(5)
    ],
    # Bughotu Genesis 1:3-7 (AI translations for parallel fetch testing)
    *[
        {
            "_id": f"verse_bughotu_gen_1_{v}_ai",
            "language_code": "bughotu",
            "book_code": "genesis",
            "chapter": 1,
            "verse": v,
            "translation_type": "ai",
            "translated_text": _BUGHOTU_GENESIS_VERSES_AI[v],
            "human_verified": False,
            "created_at": datetime(2024, 1, 1),
        }
        for v in [3, 4, 5, 6, 7]
    ],
    # Bughotu Genesis 1:5 HUMAN version (to test human > ai priority)
    {
        "_id": "verse_bughotu_gen_1_5_human",
        "language_code": "bughotu",
        "book_code": "genesis",
        "chapter": 1,
        "verse": 5,
        "translation_type": "human",
        "translated_text": _BUGHOTU_GENESIS_VERSE_5_HUMAN,
        "human_verified": True,
        "created_at": datetime(2024, 1, 1),
    },
]

TEST_DICTIONARIES = [
    {
        "_id": "dict_heb_human",
        "language_code": "heb",
        "language_name": "Hebrew",
        "translation_type": "human",
        "dictionary_name": "Hebrew Human Dictionary",
        "entry_count": 2,
        "entries": [
            {
                "word": "בראשית",
                "definition": "In the beginning",
                "part_of_speech": "noun",
                "examples": ["Genesis 1:1"],
                "human_verified": True,
                "created_at": datetime(2024, 1, 1),
            },
            {
                "word": "אלהים",
                "definition": "God, gods",
                "part_of_speech": "noun",
                "examples": ["Genesis 1:1"],
                "human_verified": False,
                "created_at": datetime(2024, 1, 1),
            },
        ],
        "created_at": datetime(2024, 1, 1),
    }
]

TEST_GRAMMAR_SYSTEMS = [
    {
        "_id": "grammar_heb_human",
        "language_code": "heb",
        "language_name": "Hebrew",
        "translation_type": "human",
        "grammar_system_name": "Hebrew Grammar System",
        "categories": {
            "phonology": {
                "description": "Hebrew sound system",
                "subcategories": ["consonants", "vowels"],
                "notes": ["22 consonant phonemes"],
                "examples": ["aleph is a glottal stop"],
            },
            "morphology": {
                "description": "Hebrew word formation",
                "subcategories": [],
                "notes": [],
                "examples": [],
            },
            "syntax": {"description": "", "subcategories": [], "notes": [], "examples": []},
            "semantics": {"description": "", "subcategories": [], "notes": [], "examples": []},
            "discourse": {"description": "", "subcategories": [], "notes": [], "examples": []},
        },
        "created_at": datetime(2024, 1, 1),
    }
]


class AsyncIterator:
    """Helper to mock async iteration (for cursor operations)"""

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
def mock_mcp_db():
    """
    Mock MongoDBConnector for MCP server tests.

    Provides realistic test data matching schema_definition.py.
    Collections: languages, bible_books, bible_texts, dictionaries, grammar_systems
    """
    db = MagicMock()

    # Collection data lookup
    _collections_data = {
        "languages": TEST_LANGUAGES,
        "bible_books": TEST_BIBLE_BOOKS,
        "bible_texts": TEST_BIBLE_TEXTS,
        "dictionaries": TEST_DICTIONARIES,
        "grammar_systems": TEST_GRAMMAR_SYSTEMS,
    }

    # Collection mocks cache
    _collection_cache = {}

    def make_collection_mock(name):
        """Create a mock collection with find_one, find, etc."""
        data = _collections_data.get(name, [])
        coll = MagicMock()

        # find_one: return first matching doc or None
        async def mock_find_one(query):
            for doc in data:
                if _matches_query(doc, query):
                    return doc
            return None

        coll.find_one = AsyncMock(side_effect=mock_find_one)

        # find: return cursor-like object that respects skip/limit/sort
        def mock_find(query=None):
            results = []
            query = query or {}
            for doc in data:
                if _matches_query(doc, query):
                    results.append(doc)

            # Create cursor with state tracking
            class MockCursor:
                def __init__(self, docs):
                    self._docs = list(docs)  # Copy to avoid mutation
                    self._skip = 0
                    self._limit = None

                def sort(self, key_or_list, direction=None):
                    """
                    Sort documents by field(s).

                    Supports:
                    - sort("field") or sort("field", 1/-1)
                    - sort([("field1", 1), ("field2", -1)])
                    """
                    if isinstance(key_or_list, str):
                        sort_spec = [(key_or_list, direction if direction else 1)]
                    elif isinstance(key_or_list, list):
                        sort_spec = key_or_list
                    else:
                        sort_spec = list(key_or_list.items())

                    def compare(a, b):
                        for field, dir in sort_spec:
                            a_val = a.get(field)
                            b_val = b.get(field)
                            # Handle None values (sort to end)
                            if a_val is None and b_val is None:
                                continue
                            if a_val is None:
                                return dir
                            if b_val is None:
                                return -dir
                            # Compare values
                            if a_val < b_val:
                                return -dir
                            if a_val > b_val:
                                return dir
                        return 0

                    self._docs = sorted(self._docs, key=cmp_to_key(compare))
                    return self

                def skip(self, n):
                    self._skip = n
                    return self

                def limit(self, n):
                    self._limit = n
                    return self

                async def to_list(self, length=None):
                    docs = self._docs[self._skip:]
                    if self._limit is not None:
                        docs = docs[: self._limit]
                    return docs

                def __aiter__(self):
                    docs = self._docs[self._skip:]
                    if self._limit is not None:
                        docs = docs[: self._limit]
                    return AsyncIterator(docs)

            return MockCursor(results)

        coll.find = MagicMock(side_effect=mock_find)

        # count_documents
        async def mock_count(query=None):
            query = query or {}
            count = 0
            for doc in data:
                if _matches_query(doc, query):
                    count += 1
            return count

        coll.count_documents = AsyncMock(side_effect=mock_count)

        # update_one, insert_one for write operations
        coll.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id="new_id"))

        return coll

    def get_or_create_collection(name):
        if name not in _collection_cache:
            _collection_cache[name] = make_collection_mock(name)
        return _collection_cache[name]

    db.get_collection = MagicMock(side_effect=get_or_create_collection)
    db._collection_cache = _collection_cache
    db._collections_data = _collections_data  # Expose for test modifications

    return db
