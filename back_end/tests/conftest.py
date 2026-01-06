# tests/conftest.py
"""Pytest configuration for USFM parser tests."""

import sys
from pathlib import Path

# Add the back_end directory to Python path for imports
# This allows imports like `from utils.usfm_parser import ...`
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))