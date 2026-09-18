#!/usr/bin/env python3
"""Regenerate Ali Sakr Session 041 review PDF."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from match_review_pdf import build_pdf

if __name__ == "__main__":
    print(build_pdf("ali_sakr_session_041"))
