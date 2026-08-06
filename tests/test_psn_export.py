import csv
import os

import pytest

import psn_export
from psn_client import GameRecord, PSNAuthenticationError


class TestResolveNpsso:
    def test_prefers_cli_value(self, monkeypatch):
        monkeypatch.setenv("PSN_NPSSO", "from-env")
        assert psn_export.resolve_npsso("from-cli") == "from-cli"

    def test_falls_back_to_env_var(self, monkeypatch):
        monkeypatch.setenv("PSN_NPSSO", "from-env")
        assert psn_export.resolve_npsso(None) == "from-env"

    def test_empty_when_neither_set(self, monkeypatch):
        monkeypatch.delenv("PSN_NPSSO", raising=False)
        assert psn_export.resolve_npsso(None) == ""


class TestMain:
    def _sample_games(self):
        return [
            GameRecord(title="A", platform="PlayStation", hours=0, completed_at="", platinum=False),
            GameRecord(title="B", platform="PlayStation", hours=5, completed_at="2024-01-01", platinum=True),
        ]

    def test_writes_csv_and_returns_zero(self, tmp_path, mocker):
        output = tmp_path / "games.csv"
        mock_client = mocker.MagicMock()
        mock_client.fetch_library.return_value = self._sample_games()
        mocker.patch("psn_export.PSNClient", return_value=mock_client)

        exit_code = psn_export.main(["--npsso", "f" * 64, "--output", str(output)])

        assert exit_code == 0
        assert output.exists()
        with open(output, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[0][0] == "title"
        assert len(rows) == 3  # header + 2 games

    def test_min_hours_filters_output(self, tmp_path, mocker):
        output = tmp_path / "games.csv"
        mock_client = mocker.MagicMock()
        mock_client.fetch_library.return_value = self._sample_games()
        mocker.patch("psn_export.PSNClient", return_value=mock_client)

        exit_code = psn_export.main(
            ["--npsso", "f" * 64, "--output", str(output), "--min-hours", "1"]
        )

        assert exit_code == 0
        with open(output, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert len(rows) == 2  # header + 1 game (only "B" has >=1 hour)
        assert rows[1][0] == "B"

    def test_default_output_filename_used_when_not_specified(self, tmp_path, mocker, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_client = mocker.MagicMock()
        mock_client.fetch_library.return_value = self._sample_games()
        mocker.patch("psn_export.PSNClient", return_value=mock_client)

        exit_code = psn_export.main(["--npsso", "f" * 64])

        assert exit_code == 0
        produced = [p for p in os.listdir(tmp_path) if p.startswith("psn_library_export_")]
        assert len(produced) == 1

    def test_authentication_error_on_construction_returns_nonzero(self, mocker):
        mocker.patch(
            "psn_export.PSNClient",
            side_effect=PSNAuthenticationError("invalid or expired npsso token"),
        )
        exit_code = psn_export.main(["--npsso", "bad-token"])
        assert exit_code == 1

    def test_authentication_error_during_fetch_returns_nonzero(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.fetch_library.side_effect = PSNAuthenticationError("expired mid-run")
        mocker.patch("psn_export.PSNClient", return_value=mock_client)
        exit_code = psn_export.main(["--npsso", "f" * 64])
        assert exit_code == 1
