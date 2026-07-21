from typing import Optional

import pandas as pd


def load_csv(path: str, encoding: Optional[str] = None) -> pd.DataFrame:
    """Load CSV with best-effort handling of BOM/CRLF."""
    if encoding is None:
        # Try utf-8-sig first to strip BOM if present
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(path)
    else:
        return pd.read_csv(path, encoding=encoding)

