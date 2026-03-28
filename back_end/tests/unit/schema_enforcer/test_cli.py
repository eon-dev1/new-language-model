"""
Tests for cli.py - CLI argument parsing and execution.

TDD Step 5: These tests are written BEFORE the implementation.
Run with: pytest tests/unit/schema_enforcer/test_cli.py -v
"""

import pytest


class TestCliArgumentParsing:
    """Tests for CLI argument parsing"""

    def test_cli_dry_run_flag(self):
        """--dry-run sets dry_run=True"""
        from utils.schema_enforcer.cli import parse_args

        args = parse_args(["--dry-run"])
        assert args.dry_run is True
        assert args.enforce is False

    def test_cli_enforce_flag(self):
        """--enforce sets enforce=True"""
        from utils.schema_enforcer.cli import parse_args

        args = parse_args(["--enforce"])
        assert args.enforce is True

    def test_cli_output_flag(self):
        """--output sets output path"""
        from utils.schema_enforcer.cli import parse_args

        args = parse_args(["--dry-run", "--output", "report.json"])
        assert args.output == "report.json"

    def test_cli_sample_size_flag(self):
        """--sample-size sets validation sample size"""
        from utils.schema_enforcer.cli import parse_args

        args = parse_args(["--dry-run", "--sample-size", "500"])
        assert args.sample_size == 500
