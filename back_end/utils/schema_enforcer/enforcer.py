"""
SchemaEnforcer - Async schema enforcement for MongoDB.

Compares actual database state against EXPECTED_COLLECTIONS schema,
creates missing indexes/collections (in enforce mode), and reports drift.
"""

from datetime import datetime, timezone

from utils.schema_enforcer.schema_definition import (
    EXPECTED_COLLECTIONS,
    DEPRECATED_COLLECTIONS,
    REQUIRED_SEED_DATA,
)
from utils.schema_enforcer.report import EnforcementReport
from utils.schema_enforcer.validators import validate_document


class SchemaEnforcer:
    """
    Async schema enforcer for MongoDB.

    Usage:
        enforcer = SchemaEnforcer(db_connector, dry_run=True)
        report = await enforcer.enforce()
        print(report.summary())
    """

    def __init__(self, db, dry_run: bool = True, sample_size: int = 100):
        """
        Initialize the schema enforcer.

        Args:
            db: MongoDBConnector instance
            dry_run: If True, only report issues. If False, create missing items.
            sample_size: Number of documents to validate per collection.
        """
        self.db = db
        self.dry_run = dry_run
        self.sample_size = sample_size
        self.report = EnforcementReport()

    async def enforce(self) -> EnforcementReport:
        """
        Run schema enforcement.

        Returns:
            EnforcementReport with results
        """
        # Get current state
        existing_collections = await self._list_collections()

        # Check collections
        await self._check_collections(existing_collections)

        # Check indexes for each expected collection
        await self._check_indexes(existing_collections)

        # Check for deprecated collections
        await self._check_deprecated(existing_collections)

        # Check for unexpected collections
        self._check_unexpected(existing_collections)

        # Sample validate documents
        await self._sample_validate_documents()

        # Seed required data
        await self._seed_required_data()

        return self.report

    async def _list_collections(self) -> list[str]:
        """Get list of collection names from database"""
        database = self.db.get_database()
        return await database.list_collection_names()

    async def _check_collections(self, existing: list[str]) -> None:
        """Check that all expected collections exist"""
        for coll_name, schema in EXPECTED_COLLECTIONS.items():
            if schema.get("required", True) and coll_name not in existing:
                self.report.add_missing("collection", coll_name)

                if not self.dry_run:
                    # Creating a collection is implicit in MongoDB when
                    # you insert a document or create an index.
                    # We'll create it via the first index creation.
                    pass

    async def _check_indexes(self, existing_collections: list[str]) -> None:
        """Check that all expected indexes exist"""
        for coll_name, schema in EXPECTED_COLLECTIONS.items():
            collection_exists = coll_name in existing_collections

            if not collection_exists:
                if self.dry_run:
                    # In dry-run mode, skip index checks for missing collections
                    continue
                # In enforce mode, we'll create collection via first index creation

            coll = self.db.get_collection(coll_name)

            if collection_exists:
                existing_indexes = await coll.index_information()
                existing_index_names = set(existing_indexes.keys())
            else:
                existing_index_names = set()  # Collection will be created

            for index_spec in schema.get("indexes", []):
                index_name = index_spec.get("name")
                if index_name and index_name not in existing_index_names:
                    full_name = f"{coll_name}.{index_name}"
                    self.report.add_missing("index", full_name)

                    if not self.dry_run:
                        # Create the index (implicitly creates collection if missing)
                        keys = index_spec["keys"]
                        unique = index_spec.get("unique", False)
                        await coll.create_index(keys, name=index_name, unique=unique)
                        self.report.mark_created("index", full_name)

                        # If collection was missing, mark it as created too
                        if not collection_exists:
                            self.report.mark_created("collection", coll_name)
                            collection_exists = True  # Only mark once

    async def _check_deprecated(self, existing: list[str]) -> None:
        """Warn about deprecated collections"""
        for coll_name in DEPRECATED_COLLECTIONS:
            if coll_name in existing:
                coll = self.db.get_collection(coll_name)
                count = await coll.count_documents({})
                self.report.add_warning(
                    f"Deprecated collection '{coll_name}' exists with {count} documents"
                )

    def _check_unexpected(self, existing: list[str]) -> None:
        """Warn about unexpected collections (not in schema)"""
        expected_names = set(EXPECTED_COLLECTIONS.keys())
        deprecated_names = set(DEPRECATED_COLLECTIONS)

        for coll_name in existing:
            # Skip system collections
            if coll_name.startswith("system."):
                continue

            if coll_name not in expected_names and coll_name not in deprecated_names:
                self.report.add_warning(
                    f"Unexpected collection '{coll_name}' found (not in schema)"
                )

    async def _sample_validate_documents(self) -> None:
        """
        Validate a sample of documents from each collection.

        CONSTRAINT: Must use `async for doc in cursor` pattern, NOT `to_list()`.
        This ensures compatibility with the AsyncIterator mock in tests.
        """
        for coll_name, schema in EXPECTED_COLLECTIONS.items():
            try:
                coll = self.db.get_collection(coll_name)

                # Sample documents using async iteration (not to_list)
                cursor = coll.aggregate([{"$sample": {"size": self.sample_size}}])
                async for doc in cursor:
                    issues = validate_document(doc, schema, coll_name)
                    for issue in issues:
                        self.report.add_warning(f"{coll_name}: {issue}")
            except Exception:
                # Collection might not exist or be empty
                pass

    async def _seed_required_data(self) -> None:
        """
        Insert required seed data if missing.

        Checks REQUIRED_SEED_DATA for documents that must exist (e.g., English
        base language) and inserts them if not present. Idempotent - safe to
        run multiple times.
        """
        for coll_name, documents in REQUIRED_SEED_DATA.items():
            coll = self.db.get_collection(coll_name)

            for doc_template in documents:
                # Determine unique identifier field based on collection
                # For languages, use language_code
                if coll_name == "languages":
                    identifier_field = "language_code"
                else:
                    # Default fallback - could be extended for other collections
                    identifier_field = "_id"

                identifier_value = doc_template.get(identifier_field)
                if not identifier_value:
                    continue

                # Check if document already exists
                existing = await coll.find_one({identifier_field: identifier_value})

                if existing is None:
                    # Document is missing
                    seed_name = f"{coll_name}/{identifier_value}"
                    self.report.add_missing("seed_data", seed_name)

                    if not self.dry_run:
                        # Create a copy to avoid modifying the template
                        doc = dict(doc_template)

                        # Add timestamps
                        now = datetime.now(timezone.utc)
                        doc["created_at"] = now
                        if "translation_levels" in doc and "human" in doc["translation_levels"]:
                            doc["translation_levels"]["human"]["last_updated"] = now

                        await coll.insert_one(doc)
                        self.report.mark_created("seed_data", seed_name)
