import csv
from datetime import date

import pytest

from csv_writer import (
    HEADERS,
    filter_by_min_hours,
    game_record_to_row,
    generate_default_filename,
    write_csv,
)
from psn_client import GameRecord


def make_game(**overrides) -> GameRecord:
    defaults = dict(
        title="Bloodborne",
        platform="PlayStation",
        hours=42,
        completed_at="2024-03-01",
        platinum=True,
    )
    defaults.update(overrides)
    return GameRecord(**defaults)


class TestGenerateDefaultFilename:
    def test_uses_iso_date(self):
        assert generate_default_filename(date(2026, 8, 6)) == "psn_library_export_2026-08-06.csv"

    def test_defaults_to_today(self):
        assert generate_default_filename().startswith("psn_library_export_")
        assert generate_default_filename().endswith(".csv")


class TestFilterByMinHours:
    def test_keeps_games_at_or_above_threshold(self):
        games = [make_game(title="A", hours=0), make_game(title="B", hours=1), make_game(title="C", hours=10)]
        result = filter_by_min_hours(games, min_hours=1)
        assert [g.title for g in result] == ["B", "C"]

    def test_zero_min_hours_keeps_everything(self):
        games = [make_game(title="A", hours=0), make_game(title="B", hours=5)]
        assert filter_by_min_hours(games, min_hours=0) == games


class TestGameRecordToRow:
    def test_column_order_matches_headers(self):
        row = game_record_to_row(make_game())
        assert len(row) == len(HEADERS)

    def test_platinum_true(self):
        row = game_record_to_row(make_game(platinum=True))
        assert row[HEADERS.index("Platinum")] == "True"

    def test_platinum_false(self):
        row = game_record_to_row(make_game(platinum=False))
        assert row[HEADERS.index("Platinum")] == "False"

    def test_empty_completed_at_is_empty_string_not_none(self):
        row = game_record_to_row(make_game(completed_at=""))
        assert row[HEADERS.index("Completed At")] == ""

    def test_none_completed_at_is_empty_string_not_none(self):
        row = game_record_to_row(make_game(completed_at=None))
        value = row[HEADERS.index("Completed At")]
        assert value == ""
        assert value != "None"

    def test_optional_columns_always_blank(self):
        row = game_record_to_row(make_game())
        assert row[HEADERS.index("User Score")] == ""
        assert row[HEADERS.index("Status")] == ""
        assert row[HEADERS.index("Favorite")] == ""
        assert row[HEADERS.index("Review")] == ""

    def test_hours_written_as_plain_int_string(self):
        row = game_record_to_row(make_game(hours=123))
        assert row[HEADERS.index("Time Played")] == "123"


class TestWriteCsv:
    def test_headers_and_order(self, tmp_path):
        output = tmp_path / "out.csv"
        write_csv([make_game()], str(output))
        with open(output, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header_row = next(reader)
        assert header_row == [
            "Name",
            "Platform",
            "Time Played",
            "Completed At",
            "Platinum",
            "User Score",
            "Status",
            "Favorite",
            "Review",
        ]

    def test_writes_expected_row_count_and_returns_it(self, tmp_path):
        output = tmp_path / "out.csv"
        games = [make_game(title="A", hours=0), make_game(title="B", hours=5)]
        written = write_csv(games, str(output), min_hours=1)
        assert written == 1
        with open(output, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert len(rows) == 2  # header + 1 game
        assert rows[1][0] == "B"

    def test_no_none_or_null_strings_in_output(self, tmp_path):
        output = tmp_path / "out.csv"
        write_csv([make_game(completed_at=None, platform=None)], str(output))
        content = output.read_text(encoding="utf-8")
        assert "None" not in content
        assert "null" not in content.lower().replace("nullable", "")

    def test_utf8_encoding(self, tmp_path):
        output = tmp_path / "out.csv"
        write_csv([make_game(title="ゼルダの伝説")], str(output))
        content = output.read_text(encoding="utf-8")
        assert "ゼルダの伝説" in content
