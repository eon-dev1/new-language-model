"""
EnforcementReport - Accumulates results from schema enforcement operations.

Provides:
- Tracking of missing/created collections and indexes
- Warning accumulation
- JSON serialization for machine consumption
- Human-readable summary
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from utils.schema_enforcer.schema_definition import SCHEMA_VERSION


@dataclass
class EnforcementReport:
    """
    Accumulates results from schema enforcement.

    Usage:
        report = EnforcementReport()
        report.add_missing("index", "bible_texts.verse_lookup")
        report.add_warning("Deprecated collection found")

        # After enforcement creates items:
        report.mark_created("index", "bible_texts.verse_lookup")

        print(report.summary())
        json_data = report.to_json()
    """

    # Missing items (found during check)
    missing_collections: list[str] = field(default_factory=list)
    missing_indexes: list[str] = field(default_factory=list)
    missing_seed_data: list[str] = field(default_factory=list)

    # Created items (after enforcement, if not dry-run)
    created_collections: list[str] = field(default_factory=list)
    created_indexes: list[str] = field(default_factory=list)
    created_seed_data: list[str] = field(default_factory=list)

    # Warnings (deprecated, unexpected, validation issues)
    warnings: list[str] = field(default_factory=list)

    # Metadata
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = field(default=SCHEMA_VERSION)

    def add_missing(self, item_type: str, name: str) -> None:
        """Record a missing item (collection, index, or seed_data)"""
        if item_type == "collection":
            if name not in self.missing_collections:
                self.missing_collections.append(name)
        elif item_type == "index":
            if name not in self.missing_indexes:
                self.missing_indexes.append(name)
        elif item_type == "seed_data":
            if name not in self.missing_seed_data:
                self.missing_seed_data.append(name)
        else:
            raise ValueError(f"Unknown item type: {item_type}")

    def mark_created(self, item_type: str, name: str) -> None:
        """Move item from missing to created (after enforcement)"""
        if item_type == "collection":
            if name in self.missing_collections:
                self.missing_collections.remove(name)
            if name not in self.created_collections:
                self.created_collections.append(name)
        elif item_type == "index":
            if name in self.missing_indexes:
                self.missing_indexes.remove(name)
            if name not in self.created_indexes:
                self.created_indexes.append(name)
        elif item_type == "seed_data":
            if name in self.missing_seed_data:
                self.missing_seed_data.remove(name)
            if name not in self.created_seed_data:
                self.created_seed_data.append(name)
        else:
            raise ValueError(f"Unknown item type: {item_type}")

    def add_warning(self, message: str) -> None:
        """Add a warning message"""
        self.warnings.append(message)

    def to_json(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary"""
        return {
            "schema_version": self.schema_version,
            "timestamp": self.timestamp.isoformat(),
            "missing_collections": self.missing_collections,
            "missing_indexes": self.missing_indexes,
            "missing_seed_data": self.missing_seed_data,
            "created_collections": self.created_collections,
            "created_indexes": self.created_indexes,
            "created_seed_data": self.created_seed_data,
            "warnings": self.warnings,
            "summary": {
                "total_missing": len(self.missing_collections)
                + len(self.missing_indexes)
                + len(self.missing_seed_data),
                "total_created": len(self.created_collections)
                + len(self.created_indexes)
                + len(self.created_seed_data),
                "total_warnings": len(self.warnings),
            },
        }

    def summary(self) -> str:
        """Generate human-readable summary"""
        lines = [
            "=== Schema Enforcement Report ===",
            f"Schema Version: {self.schema_version}",
            f"Timestamp: {self.timestamp.isoformat()}",
            "",
        ]

        # Missing items
        if self.missing_collections or self.missing_indexes or self.missing_seed_data:
            lines.append("MISSING:")
            for coll in self.missing_collections:
                lines.append(f"  ✗ Collection: {coll}")
            for idx in self.missing_indexes:
                lines.append(f"  ✗ Index: {idx}")
            for seed in self.missing_seed_data:
                lines.append(f"  ✗ Seed data: {seed}")
            lines.append("")

        # Created items
        if self.created_collections or self.created_indexes or self.created_seed_data:
            lines.append("CREATED:")
            for coll in self.created_collections:
                lines.append(f"  ✓ Collection: {coll}")
            for idx in self.created_indexes:
                lines.append(f"  ✓ Index: {idx}")
            for seed in self.created_seed_data:
                lines.append(f"  ✓ Seed data: {seed}")
            lines.append("")

        # Warnings
        if self.warnings:
            lines.append("WARNINGS:")
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")
            lines.append("")

        # Summary counts
        lines.append("SUMMARY:")
        lines.append(
            f"  Missing: {len(self.missing_collections)} collections, "
            f"{len(self.missing_indexes)} indexes, "
            f"{len(self.missing_seed_data)} seed data"
        )
        lines.append(
            f"  Created: {len(self.created_collections)} collections, "
            f"{len(self.created_indexes)} indexes, "
            f"{len(self.created_seed_data)} seed data"
        )
        lines.append(f"  Warnings: {len(self.warnings)}")

        return "\n".join(lines)
