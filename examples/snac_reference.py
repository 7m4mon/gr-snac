#!/usr/bin/env python3
import sys
from pathlib import Path
source = Path(__file__).resolve().parents[1] / "python" / "gr_snac_core"
if source.is_dir():
    sys.path.insert(0, str(source.parent))
from gr_snac_core.cli import run

if __name__ == "__main__":
    run(reference=True)
