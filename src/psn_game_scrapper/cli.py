#!/usr/bin/env python3
"""CLI entry point: export a PSN game library to a GRAVK-compatible CSV.

Usage:
    psn-export --npsso <token> --output games.csv [--min-hours 0] [--force]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional

from psnawp_api.core.psnawp_exceptions import PSNAWPError

from .client import PSNAuthenticationError, PSNClient
from .csv_writer import generate_default_filename, write_csv

logger = logging.getLogger("psn_export")


def _non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer")
    if number < 0:
        raise argparse.ArgumentTypeError("must be 0 or greater")
    return number


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
        type=_non_negative_int,
        default=0,
        help="Only export games with at least this many hours played (default: 0, export everything).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser.parse_args(argv)


def resolve_npsso(cli_value: Optional[str]) -> str:
    return cli_value or os.environ.get("PSN_NPSSO", "")


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    npsso = resolve_npsso(args.npsso)
    output_path = args.output or generate_default_filename()

    if os.path.exists(output_path) and not args.force:
        logger.error(
            "%s already exists. Pass --force to overwrite it or --output to pick another path.",
            output_path,
        )
        return 1

    try:
        client = PSNClient(npsso)
    except PSNAuthenticationError as exc:
        logger.error(str(exc))
        return 1

    logger.info("Fetching PSN library...")

    def on_progress(stage: str, count: int) -> None:
        if count % 25 == 0:
            logger.info("Fetched %s %s...", count, stage)

    try:
        games = client.fetch_library(progress_callback=on_progress)
    except PSNAuthenticationError as exc:
        logger.error(str(exc))
        return 1
    except PSNAWPError as exc:
        logger.error("PSN request failed: %s", exc)
        return 1

    logger.info("Fetched %s titles", len(games))

    try:
        written = write_csv(games, output_path, min_hours=args.min_hours)
    except OSError as exc:
        logger.error("Could not write %s: %s", output_path, exc)
        return 1
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
