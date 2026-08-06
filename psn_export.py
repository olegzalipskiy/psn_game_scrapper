#!/usr/bin/env python3
"""CLI entry point: export a PSN game library to a GRAVK-compatible CSV.

Usage:
    python psn_export.py --npsso <token> --output games.csv [--min-hours 0]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional

from csv_writer import generate_default_filename, write_csv
from psn_client import PSNAuthenticationError, PSNClient

logger = logging.getLogger("psn_export")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export your PSN game library to a GRAVK-compatible CSV file."
    )
    parser.add_argument(
        "--npsso",
        default=None,
        help="PSN npsso token. Falls back to the PSN_NPSSO environment variable.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path. Defaults to psn_library_export_{YYYY-MM-DD}.csv",
    )
    parser.add_argument(
        "--min-hours",
        type=int,
        default=0,
        help="Only export games with at least this many hours played (default: 0, export everything).",
    )
    return parser.parse_args(argv)


def resolve_npsso(cli_value: Optional[str]) -> str:
    return cli_value or os.environ.get("PSN_NPSSO", "")


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    npsso = resolve_npsso(args.npsso)
    output_path = args.output or generate_default_filename()

    try:
        client = PSNClient(npsso)
    except PSNAuthenticationError as exc:
        logger.error(str(exc))
        return 1

    logger.info("Fetching PSN library...")

    def on_progress(processed: int, total: int) -> None:
        if total == 0:
            return
        if processed == total or processed % 25 == 0:
            logger.info("Processed %s/%s titles", processed, total)

    try:
        games = client.fetch_library(progress_callback=on_progress)
    except PSNAuthenticationError as exc:
        logger.error(str(exc))
        return 1

    written = write_csv(games, output_path, min_hours=args.min_hours)
    logger.info(
        "Wrote %s of %s games to %s (min-hours=%s)",
        written,
        len(games),
        output_path,
        args.min_hours,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
