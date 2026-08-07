"""CSV formatting and writing for GRAVK-compatible library exports."""

from __future__ import annotations

import csv
from datetime import date
from typing import List, Optional, Sequence

from .client import GameRecord

HEADERS: List[str] = [
    "title",
    "hours",
    "completedAt",
    "platform",
    "status",
    "userScore",
    "platinum",
    "steamDeck",
    "favorite",
]


def generate_default_filename(today: Optional[date] = None) -> str:
    """Build the default output filename: psn_library_export_{YYYY-MM-DD}.csv."""
    if today is None:
        today = date.today()
    return f"psn_library_export_{today.isoformat()}.csv"


def filter_by_min_hours(games: Sequence[GameRecord], min_hours: int) -> List[GameRecord]:
    """Keep only games with hours >= min_hours."""
    return [game for game in games if game.hours >= min_hours]


def _empty_if_falsy(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.lower() in ("none", "null") else text


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def game_record_to_row(game: GameRecord) -> List[str]:
    """Convert a GameRecord into a CSV row matching HEADERS, column for column.

    status, userScore, and favorite have no source in the PSN API and are
    always left empty: an empty/unrecognized status lets GRAVK determine it
    automatically from hours played, per the GRAVK import template. steamDeck
    is always "false" since PSN games are never played on Steam Deck.
    """
    return [
        _empty_if_falsy(game.title),
        str(game.hours),
        _empty_if_falsy(game.completed_at),
        _empty_if_falsy(game.platform),
        "",  # status - left empty so GRAVK auto-detects it from hours
        "",  # userScore - no source in the PSN API
        _bool_str(game.platinum),
        _bool_str(False),  # steamDeck - PSN games are never Steam Deck
        "",  # favorite - left empty, defaults to not-favorited in GRAVK
    ]


def write_csv(games: Sequence[GameRecord], output_path: str, min_hours: int = 0) -> int:
    """Write games to a CSV file at output_path, applying the min_hours filter.

    :returns: The number of rows written (excluding the header).
    """
    filtered = filter_by_min_hours(games, min_hours)
    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(HEADERS)
        for game in filtered:
            writer.writerow(game_record_to_row(game))
    return len(filtered)
