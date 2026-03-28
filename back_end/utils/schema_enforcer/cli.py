"""
CLI interface for schema enforcement.

Usage:
    python -m utils.schema_enforcer --dry-run
    python -m utils.schema_enforcer --enforce
    python -m utils.schema_enforcer --enforce --verbose --sample-size 500
    python -m utils.schema_enforcer --enforce --output report.json
"""

import argparse
import asyncio
import json
import sys
from typing import Optional

from utils.schema_enforcer.enforcer import SchemaEnforcer


def parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """
    Parse command line arguments.

    Args:
        args: List of arguments (defaults to sys.argv[1:])

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog="schema_enforcer",
        description="Enforce MongoDB schema against expected collections",
    )

    # Mode flags (mutually exclusive in practice, but both can be False)
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Check schema without making changes (default mode if neither specified)",
    )

    parser.add_argument(
        "--enforce",
        action="store_true",
        default=False,
        help="Create missing collections and indexes",
    )

    # Options
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Show detailed progress",
    )

    parser.add_argument(
        "--sample-size",
        dest="sample_size",
        type=int,
        default=100,
        help="Number of documents to validate per collection (default: 100)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Write JSON report to file",
    )

    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Only check specific collection (not yet implemented)",
    )

    return parser.parse_args(args)


async def run(args: argparse.Namespace) -> int:
    """
    Run the schema enforcer with parsed arguments.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code (0 = success, 1 = issues found)
    """
    from db_connector.connection import get_mongodb_connector

    # Determine dry_run mode
    # If --enforce is specified, dry_run=False
    # Otherwise, default to dry_run=True
    dry_run = not args.enforce

    if args.verbose:
        print(f"Mode: {'dry-run' if dry_run else 'enforce'}")
        print(f"Sample size: {args.sample_size}")

    try:
        # Get database connection
        db = await get_mongodb_connector()

        # Create enforcer
        enforcer = SchemaEnforcer(
            db=db,
            dry_run=dry_run,
            sample_size=args.sample_size,
        )

        # Run enforcement
        report = await enforcer.enforce()

        # Output results
        if args.verbose:
            print(report.summary())
        else:
            # Just print summary line
            json_data = report.to_json()
            summary = json_data["summary"]
            print(
                f"Missing: {summary['total_missing']}, "
                f"Created: {summary['total_created']}, "
                f"Warnings: {summary['total_warnings']}"
            )

        # Write JSON output if requested
        if args.output:
            with open(args.output, "w") as f:
                json.dump(report.to_json(), f, indent=2)
            if args.verbose:
                print(f"\nReport written to: {args.output}")

        # Exit with error if there are issues
        if report.missing_collections or report.missing_indexes:
            return 1

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> None:
    """Entry point for CLI"""
    args = parse_args()
    exit_code = asyncio.run(run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
