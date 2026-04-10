from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

for path in (ROOT, SRC):
    as_text = str(path)
    if as_text not in sys.path:
        sys.path.insert(0, as_text)
