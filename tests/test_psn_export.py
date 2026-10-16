import csv
import os

import pytest

from psn_game_scrapper import cli as psn_export
from psnawp_api.core.psnawp_exceptions import PSNAWPServerError

from psn_game_scrapper.client import GameRecord, PSNAuthenticationError


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
        mocker.patch("psn_game_scrapper.cli.PSNClient", return_value=mock_client)

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
        mocker.patch("psn_game_scrapper.cli.PSNClient", return_value=mock_client)

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
        mocker.patch("psn_game_scrapper.cli.PSNClient", return_value=mock_client)

        exit_code = psn_export.main(["--npsso", "f" * 64])

        assert exit_code == 0
        produced = [p for p in os.listdir(tmp_path) if p.startswith("psn_library_export_")]
        assert len(produced) == 1

    def test_authentication_error_on_construction_returns_nonzero(self, mocker):
        mocker.patch(
            "psn_game_scrapper.cli.PSNClient",
            side_effect=PSNAuthenticationError("invalid or expired npsso token"),
        )
        exit_code = psn_export.main(["--npsso", "bad-token"])
        assert exit_code == 1

    def test_authentication_error_during_fetch_returns_nonzero(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.fetch_library.side_effect = PSNAuthenticationError("expired mid-run")
        mocker.patch("psn_game_scrapper.cli.PSNClient", return_value=mock_client)
        exit_code = psn_export.main(["--npsso", "f" * 64])
        assert exit_code == 1

    def _patch_client(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.fetch_library.return_value = self._sample_games()
        mocker.patch("psn_game_scrapper.cli.PSNClient", return_value=mock_client)
        return mock_client

    def test_existing_output_is_not_overwritten(self, tmp_path, mocker):
        output = tmp_path / "games.csv"
        output.write_text("keep me")
        client_cls = mocker.patch("psn_game_scrapper.cli.PSNClient")
        assert psn_export.main(["--npsso", "f" * 64, "--output", str(output)]) == 1
        assert output.read_text() == "keep me"
        client_cls.assert_not_called()

    def test_force_overwrites_existing_output(self, tmp_path, mocker):
        output = tmp_path / "games.csv"
        output.write_text("old")
        self._patch_client(mocker)
        assert psn_export.main(["--npsso", "f" * 64, "--output", str(output), "--force"]) == 0
        assert output.read_text().startswith("title,")

    def test_negative_min_hours_rejected(self):
        with pytest.raises(SystemExit):
            psn_export.parse_args(["--min-hours", "-1"])

    def test_non_integer_min_hours_rejected(self):
        with pytest.raises(SystemExit):
            psn_export.parse_args(["--min-hours", "abc"])

    def test_psn_api_error_returns_nonzero(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.fetch_library.side_effect = PSNAWPServerError("boom")
        mocker.patch("psn_game_scrapper.cli.PSNClient", return_value=mock_client)
        assert psn_export.main(["--npsso", "f" * 64]) == 1

    def test_unwritable_output_returns_nonzero(self, tmp_path, mocker):
        self._patch_client(mocker)
        bad = tmp_path / "missing_dir" / "games.csv"
        assert psn_export.main(["--npsso", "f" * 64, "--output", str(bad)]) == 1

    def test_progress_logging_every_25(self, tmp_path, mocker, caplog):
        mock_client = mocker.MagicMock()

        def fake_fetch(progress_callback):
            for n in (1, 25, 50):
                progress_callback("titles", n)
            return self._sample_games()

        mock_client.fetch_library.side_effect = fake_fetch
        mocker.patch("psn_game_scrapper.cli.PSNClient", return_value=mock_client)
        with caplog.at_level("INFO", logger="psn_export"):
            psn_export.main(["--npsso", "f" * 64, "--output", str(tmp_path / "g.csv")])
        assert "Fetched 25 titles..." in caplog.text
        assert "Fetched 1 titles..." not in caplog.text
