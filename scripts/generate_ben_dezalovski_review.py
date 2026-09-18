#!/usr/bin/env python3
"""Regenerate Ben Dezalovski (Club Ohio vs Toronto FC) match review PDF."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from match_review_pdf import build_pdf

if __name__ == "__main__":
    print(build_pdf("ben_dezalovski_toronto_fc"))
