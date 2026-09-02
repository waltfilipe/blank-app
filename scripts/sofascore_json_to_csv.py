#!/usr/bin/env python3
"""Convert SofaScore event JSON (passes, dribbles, defensive, ball-carries) to CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

EVENT_CATEGORIES = ("passes", "dribbles", "defensive", "ball-carries")

CSV_COLUMNS = (
    "category",
    "eventActionType",
    "isHome",
    "outcome",
    "keypass",
    "isLongBall",
    "start_x",
    "start_y",
    "end_x",
    "end_y",
)


def _coord(value: dict[str, Any] | None, axis: str) -> str:
    if not value:
        return ""
    raw = value.get(axis)
    return "" if raw is None else str(raw)


def _bool_field(value: Any) -> str:
    if value is None:
        return ""
    return str(bool(value)).lower()


def flatten_events(data: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for category in EVENT_CATEGORIES:
        for event in data.get(category, []):
            start = event.get("playerCoordinates")
            end = event.get("passEndCoordinates")

            rows.append(
                {
                    "category": category,
                    "eventActionType": str(event.get("eventActionType", "")),
                    "isHome": _bool_field(event.get("isHome")),
                    "outcome": _bool_field(event.get("outcome")),
                    "keypass": _bool_field(event.get("keypass")),
                    "isLongBall": _bool_field(event.get("isLongBall")),
                    "start_x": _coord(start, "x"),
                    "start_y": _coord(start, "y"),
                    "end_x": _coord(end, "x"),
                    "end_y": _coord(end, "y"),
                }
            )

    return rows


def convert_json_to_csv(input_path: Path, output_path: Path) -> int:
    with input_path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object with event categories at the root.")

    rows = flatten_events(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform SofaScore event JSON into a flat CSV file."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the SofaScore JSON file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output CSV path (default: same name as input with .csv extension)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    output_path = (
        args.output.expanduser().resolve()
        if args.output
        else input_path.with_suffix(".csv")
    )

    row_count = convert_json_to_csv(input_path, output_path)
    print(f"Wrote {row_count} rows to {output_path}")


if __name__ == "__main__":
    main()
