#!/usr/bin/env python3
"""Run from a checkout or after CMake installation, without GNU Radio."""
import sys
from pathlib import Path
source = Path(__file__).resolve().parents[1] / "python" / "gr_snac_core"
if source.is_dir():
    sys.path.insert(0, str(source.parent))
from gr_snac_core.cli import run

if __name__ == "__main__":
    run()
