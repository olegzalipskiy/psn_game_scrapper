from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from psn_game_scrapper.client import (
    GameRecord,
    PSNAuthenticationError,
    PSNClient,
    format_completed_at,
    has_platinum,
    hours_from_duration,
    map_platform,
    normalize_title_name,
    retry_with_backoff,
)
from psnawp_api.core.psnawp_exceptions import (
    PSNAWPAuthenticationError,
    PSNAWPInvalidTokenError,
    PSNAWPServerError,
    PSNAWPTooManyRequestsError,
)


class TestMapPlatform:
    def test_ps4_maps_to_playstation(self):
        assert map_platform("PS4") == "PlayStation"

    def test_ps5_maps_to_playstation(self):
        assert map_platform("PS5") == "PlayStation"

    def test_lowercase_ps4_still_maps(self):
        assert map_platform("ps4") == "PlayStation"

    def test_enum_like_object_with_name_attribute(self):
        fake_category = SimpleNamespace(name="PS5")
        assert map_platform(fake_category) == "PlayStation"

    def test_unknown_platform_is_returned_as_is(self):
        assert map_platform("PS3") == "PS3"

    def test_unknown_enum_like_returned_as_is(self):
        fake_category = SimpleNamespace(name="UNKNOWN")
        assert map_platform(fake_category) == "UNKNOWN"

    def test_none_returns_empty_string(self):
        assert map_platform(None) == ""


class TestHoursFromDuration:
    def test_none_is_zero(self):
        assert hours_from_duration(None) == 0

    def test_half_hour_rounds_up(self):
        assert hours_from_duration(timedelta(minutes=90)) == 2
        assert hours_from_duration(timedelta(hours=2, minutes=30)) == 3

    def test_brief_play_counts_as_one_hour(self):
        assert hours_from_duration(timedelta(minutes=25)) == 1

    def test_rounds_down_below_half_hour(self):
        assert hours_from_duration(timedelta(hours=2, minutes=20)) == 2

    def test_rounds_up_above_half_hour(self):
        assert hours_from_duration(timedelta(hours=2, minutes=45)) == 3

    def test_exact_hours(self):
        assert hours_from_duration(timedelta(hours=10)) == 10

    def test_zero_duration(self):
        assert hours_from_duration(timedelta()) == 0


class TestHasPlatinum:
    def test_dict_with_positive_platinum_count(self):
        assert has_platinum({"platinum": 1}) is True

    def test_dict_with_zero_platinum_count(self):
        assert has_platinum({"platinum": 0}) is False

    def test_object_with_platinum_attribute(self):
        trophy_set = SimpleNamespace(bronze=10, silver=5, gold=2, platinum=1)
        assert has_platinum(trophy_set) is True

    def test_object_without_platinum_earned(self):
        trophy_set = SimpleNamespace(bronze=10, silver=5, gold=2, platinum=0)
        assert has_platinum(trophy_set) is False

    def test_none_is_false(self):
        assert has_platinum(None) is False


class TestNormalizeTitleName:
    def test_strips_trademark_symbols_and_case(self):
        assert normalize_title_name("God of War™") == "god of war"

    def test_collapses_whitespace(self):
        assert normalize_title_name("  Ghost   of Tsushima  ") == "ghost of tsushima"

    def test_none_is_empty(self):
        assert normalize_title_name(None) == ""


class TestFormatCompletedAt:
    def test_none_is_empty_string(self):
        assert format_completed_at(None) == ""

    def test_formats_iso_date_only(self):
        assert format_completed_at(datetime(2024, 3, 15, 13, 45)) == "2024-03-15"


def _make_mock_func(**kwargs) -> MagicMock:
    # functools.wraps (used by retry_with_backoff) needs a __name__ to copy.
    func = MagicMock(**kwargs)
    func.__name__ = "mock_func"
    return func


class TestRetryWithBackoff:
    def test_returns_result_immediately_on_success(self, mocker):
        sleep_mock = mocker.patch("psn_game_scrapper.client.time.sleep")
        func = _make_mock_func(return_value="ok")
        wrapped = retry_with_backoff(max_retries=3, base_delay=0.01)(func)
        assert wrapped() == "ok"
        sleep_mock.assert_not_called()

    def test_retries_on_rate_limit_then_succeeds(self, mocker):
        sleep_mock = mocker.patch("psn_game_scrapper.client.time.sleep")
        func = _make_mock_func(
            side_effect=[
                PSNAWPTooManyRequestsError("rate limited"),
                PSNAWPTooManyRequestsError("rate limited"),
                "ok",
            ]
        )
        wrapped = retry_with_backoff(max_retries=3, base_delay=1.0)(func)
        result = wrapped()
        assert result == "ok"
        assert func.call_count == 3
        assert sleep_mock.call_count == 2
        # exponential backoff: 1.0, then 2.0
        sleep_mock.assert_any_call(1.0)
        sleep_mock.assert_any_call(2.0)

    def test_retries_on_server_error(self, mocker):
        mocker.patch("psn_game_scrapper.client.time.sleep")
        func = _make_mock_func(side_effect=[PSNAWPServerError("boom"), "ok"])
        wrapped = retry_with_backoff(max_retries=3, base_delay=0.01)(func)
        assert wrapped() == "ok"

    def test_raises_after_exhausting_retries(self, mocker):
        sleep_mock = mocker.patch("psn_game_scrapper.client.time.sleep")
        func = _make_mock_func(side_effect=PSNAWPTooManyRequestsError("rate limited"))
        wrapped = retry_with_backoff(max_retries=2, base_delay=0.01)(func)
        with pytest.raises(PSNAWPTooManyRequestsError):
            wrapped()
        assert func.call_count == 3  # initial attempt + 2 retries
        assert sleep_mock.call_count == 2

    def test_does_not_retry_unrelated_errors(self, mocker):
        sleep_mock = mocker.patch("psn_game_scrapper.client.time.sleep")
        func = _make_mock_func(side_effect=ValueError("not a PSN error"))
        wrapped = retry_with_backoff(max_retries=3, base_delay=0.01)(func)
        with pytest.raises(ValueError):
            wrapped()
        sleep_mock.assert_not_called()
        assert func.call_count == 1


class TestPSNClientAuthentication:
    def test_empty_npsso_raises_authentication_error(self):
        with pytest.raises(PSNAuthenticationError):
            PSNClient("")

    def test_blank_npsso_raises_authentication_error(self):
        with pytest.raises(PSNAuthenticationError):
            PSNClient("   ")

    def test_invalid_token_format_raises_authentication_error(self, mocker):
        mocker.patch(
            "psn_game_scrapper.client.PSNAWP",
            side_effect=PSNAWPInvalidTokenError("bad token"),
        )
        with pytest.raises(PSNAuthenticationError):
            PSNClient("not-a-real-npsso-token")

    def test_expired_or_invalid_token_raises_authentication_error(self, mocker):
        mocker.patch(
            "psn_game_scrapper.client.PSNAWP",
            side_effect=PSNAWPAuthenticationError("expired"),
        )
        with pytest.raises(PSNAuthenticationError):
            PSNClient("f" * 64)

    def test_valid_token_constructs_client(self, mocker):
        fake_psnawp_instance = MagicMock()
        fake_psnawp_instance.me.return_value = MagicMock()
        mocker.patch("psn_game_scrapper.client.PSNAWP", return_value=fake_psnawp_instance)
        client = PSNClient("f" * 64)
        assert client is not None


def _fake_title_stats(name, category, hours, last_played=None):
    return SimpleNamespace(
        title_id="CUSA00000",
        name=name,
        image_url=None,
        category=category,
        play_count=1,
        first_played_date_time=None,
        last_played_date_time=last_played,
        play_duration=timedelta(hours=hours),
    )


def _fake_trophy_title(name, platinum_count):
    return SimpleNamespace(
        title_name=name,
        earned_trophies=SimpleNamespace(bronze=0, silver=0, gold=0, platinum=platinum_count),
    )


class TestPSNClientFetchLibrary:
    def _make_client(self, mocker, title_stats, trophy_titles):
        fake_inner_client = MagicMock()
        fake_inner_client.title_stats.return_value = iter(title_stats)
        fake_inner_client.trophy_titles.return_value = iter(trophy_titles)
        fake_psnawp_instance = MagicMock()
        fake_psnawp_instance.me.return_value = fake_inner_client
        mocker.patch("psn_game_scrapper.client.PSNAWP", return_value=fake_psnawp_instance)
        return PSNClient("f" * 64)

    def test_merges_title_stats_with_platinum_data(self, mocker):
        last_played = datetime(2024, 1, 2, 10, 0)
        titles = [
            _fake_title_stats("Bloodborne", "PS4", 42, last_played),
            _fake_title_stats("Astro's Playroom", "PS5", 3),
        ]
        trophies = [_fake_trophy_title("Bloodborne", platinum_count=1)]

        client = self._make_client(mocker, titles, trophies)
        games = client.fetch_library()

        assert len(games) == 2
        bloodborne = next(g for g in games if g.title == "Bloodborne")
        astro = next(g for g in games if g.title == "Astro's Playroom")

        assert bloodborne.platform == "PlayStation"
        assert bloodborne.hours == 42
        assert bloodborne.completed_at == "2024-01-02"
        assert bloodborne.platinum is True

        assert astro.platinum is False
        assert astro.completed_at == ""

    def test_progress_callback_reports_fetch_stages(self, mocker):
        titles = [_fake_title_stats(f"Game {i}", "PS4", 1) for i in range(3)]
        trophies = [_fake_trophy_title("Game 0", 0), _fake_trophy_title("Game 1", 0)]
        client = self._make_client(mocker, titles, trophies)
        calls = []
        client.fetch_library(progress_callback=lambda stage, n: calls.append((stage, n)))
        assert calls == [
            ("titles", 1), ("titles", 2), ("titles", 3),
            ("trophies", 1), ("trophies", 2),
        ]

    def test_platinum_in_any_duplicate_trophy_list_counts(self, mocker):
        titles = [_fake_title_stats("Ratchet & Clank", "PS5", 10)]
        trophies = [
            _fake_trophy_title("Ratchet & Clank", platinum_count=1),
            _fake_trophy_title("Ratchet & Clank", platinum_count=0),
        ]
        games = self._make_client(mocker, titles, trophies).fetch_library()
        assert games[0].platinum is True

    def test_auth_error_during_fetch_is_wrapped(self, mocker):
        fake_inner_client = MagicMock()
        fake_inner_client.title_stats.side_effect = PSNAWPAuthenticationError("expired")
        fake_psnawp_instance = MagicMock()
        fake_psnawp_instance.me.return_value = fake_inner_client
        mocker.patch("psn_game_scrapper.client.PSNAWP", return_value=fake_psnawp_instance)

        client = PSNClient("f" * 64)
        with pytest.raises(PSNAuthenticationError):
            client.fetch_library()
