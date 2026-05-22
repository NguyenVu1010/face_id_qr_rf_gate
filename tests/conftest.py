import sys
from pathlib import Path

# Ensure repo root is importable so `from smart_gate...` works without install.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
