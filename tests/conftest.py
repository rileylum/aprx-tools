"""Shared fixtures for aprx-tools tests.

Fixtures to add here when needed:
  - sample_aprx: Path to a fixture .aprx file for round-trip tests
  - exploded_dir: Pre-exploded directory from the sample .aprx
"""

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
