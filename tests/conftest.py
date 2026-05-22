import sys
from pathlib import Path

# Ensure repo root is importable so `from smart_gate...` works without install.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary data dir layout matching production /var/lib/smart-gate."""
    (tmp_path / "clips").mkdir()
    (tmp_path / "qr").mkdir()
    return tmp_path
