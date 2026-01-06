"""
Tests for report.py - EnforcementReport dataclass.

TDD Step 2: These tests are written BEFORE the implementation.
Run with: pytest tests/unit/schema_enforcer/test_report.py -v
"""

import json
import pytest
from datetime import datetime


class TestEnforcementReport:
    """Tests for EnforcementReport dataclass"""

    def test_report_to_json_serializable(self):
        """Report converts to valid JSON"""
        from utils.schema_enforcer.report import EnforcementReport

        report = EnforcementReport()
        report.add_missing("index", "bible_texts.verse_lookup")

        # Should not raise
        json_data = report.to_json()
        json_str = json.dumps(json_data)

        assert "bible_texts.verse_lookup" in json_str
        assert "missing_indexes" in json_str

    def test_report_summary_includes_counts(self):
        """Summary shows missing/created/warning counts"""
        from utils.schema_enforcer.report import EnforcementReport

        report = EnforcementReport()
        report.add_missing("index", "test_index")
        report.add_warning("deprecated collection found")

        summary = report.summary()

        # Should contain count information
        assert "1" in summary  # At least one count
        assert "missing" in summary.lower() or "index" in summary.lower()
        assert "warning" in summary.lower()

    def test_report_tracks_created_items(self):
        """Created items recorded separately from missing"""
        from utils.schema_enforcer.report import EnforcementReport

        report = EnforcementReport()

        # First mark as missing
        report.add_missing("index", "foo_index")
        assert "foo_index" in report.missing_indexes

        # Then mark as created (after enforcement)
        report.mark_created("index", "foo_index")

        assert "foo_index" in report.created_indexes
        assert "foo_index" not in report.missing_indexes

    def test_report_timestamp_set(self):
        """Report has timestamp on creation"""
        from datetime import timezone
        from utils.schema_enforcer.report import EnforcementReport

        before = datetime.now(timezone.utc)
        report = EnforcementReport()
        after = datetime.now(timezone.utc)

        assert report.timestamp is not None
        assert before <= report.timestamp <= after

    def test_report_add_missing_collection(self):
        """Can add missing collections"""
        from utils.schema_enforcer.report import EnforcementReport

        report = EnforcementReport()
        report.add_missing("collection", "test_collection")

        assert "test_collection" in report.missing_collections

    def test_report_warnings_list(self):
        """Warnings are accumulated in a list"""
        from utils.schema_enforcer.report import EnforcementReport

        report = EnforcementReport()
        report.add_warning("First warning")
        report.add_warning("Second warning")

        assert len(report.warnings) == 2
        assert "First warning" in report.warnings
        assert "Second warning" in report.warnings

    def test_report_schema_version_included(self):
        """Report includes schema version in JSON output"""
        from utils.schema_enforcer.report import EnforcementReport

        report = EnforcementReport()
        json_data = report.to_json()

        assert "schema_version" in json_data
        assert json_data["schema_version"] == "1.0.0"
