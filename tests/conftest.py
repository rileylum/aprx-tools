import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SIMPLE_APRX = FIXTURES_DIR / "simple" / "simple.aprx"


@pytest.fixture
def simple_aprx() -> Path:
    return SIMPLE_APRX


@pytest.fixture
def exploded(tmp_path, simple_aprx) -> Path:
    """Exploded simple.aprx — reused by pack and compare tests."""
    from aprx_tools.explode import explode
    return explode(str(simple_aprx), str(tmp_path / "simple.aprx.src"))
