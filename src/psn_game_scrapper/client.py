"""PSN API client.

Wraps the third-party ``psnawp`` package (import name ``psnawp_api``) to fetch a
user's PlayStation game library (title stats + trophy data) and turn it into
plain :class:`GameRecord` objects that the rest of this project works with.
"""

from __future__ import annotations

import functools
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, TypeVar

from psnawp_api import PSNAWP
from psnawp_api.core.psnawp_exceptions import (
    PSNAWPAuthenticationError,
    PSNAWPInvalidTokenError,
    PSNAWPServerError,
    PSNAWPTooManyRequestsError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_DELAY_SECONDS = 1.0

NPSSO_HELP_URL = "https://ca.account.sony.com/api/v1/ssocookie"


class PSNAuthenticationError(Exception):
    """Raised when the npsso token is missing, malformed, or expired/invalid."""


@dataclass
class GameRecord:
    """A single row worth of data for the CSV export."""

    title: str
    platform: str
    hours: int
    completed_at: str
    platinum: bool


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry a function with exponential backoff on rate-limit/server errors."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except (PSNAWPTooManyRequestsError, PSNAWPServerError) as exc:
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(
                            "Giving up on %s after %s retries: %s",
                            func.__name__,
                            max_retries,
                            exc,
                        )
                        raise
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "%s failed (%s). Retrying in %.1fs (attempt %s/%s)",
                        func.__name__,
                        exc,
                        delay,
                        attempt,
                        max_retries,
                    )
                    time.sleep(delay)

        return wrapper

    return decorator


def normalize_title_name(name: Optional[str]) -> str:
    """Normalize a title name for fuzzy-free matching between the two PSN endpoints."""
    if not name:
        return ""
    cleaned = name.replace("™", "").replace("®", "")
    return " ".join(cleaned.lower().split())


def map_platform(category: Any) -> str:
    """Map a PSN platform/category value to the GRAVK platform name.

    PS4 and PS5 both map to ``"PlayStation"``. Anything else (including
    unknown/legacy platforms) is returned unchanged so no information is lost.
    """
    if category is None:
        return ""
    raw = getattr(category, "name", category)
    raw_str = str(raw)
    if raw_str.upper() in ("PS4", "PS5"):
        return "PlayStation"
    return raw_str


def hours_from_duration(duration: Optional[timedelta]) -> int:
    """Convert a play-duration timedelta into whole hours.

    Rounds half up to the nearest hour, but any non-zero playtime counts as at
    least 1 hour so briefly-played games are not reported as never played.
    """
    if duration is None:
        return 0
    seconds = duration.total_seconds()
    if seconds <= 0:
        return 0
    return max(1, int(seconds / 3600 + 0.5))


def has_platinum(earned_trophies: Any) -> bool:
    """Determine whether a platinum trophy has been earned.

    Accepts anything that exposes trophy counts by type: an object with a
    ``.platinum`` attribute (e.g. ``psnawp_api``'s ``TrophySet``) or a dict
    with a ``"platinum"`` key.
    """
    if earned_trophies is None:
        return False
    if isinstance(earned_trophies, dict):
        count = earned_trophies.get("platinum", 0)
    else:
        count = getattr(earned_trophies, "platinum", 0)
    return bool(count and count > 0)


def format_completed_at(dt: Optional[datetime]) -> str:
    """Format the last-played datetime as an ISO date, or "" if unavailable."""
    if dt is None:
        return ""
    return dt.date().isoformat()


def _collect(items: Iterable[T], on_item: Optional[Callable[[int], None]]) -> List[T]:
    """Drain a (lazily paginated) iterable, reporting the running count."""
    result: List[T] = []
    for item in items:
        result.append(item)
        if on_item is not None:
            on_item(len(result))
    return result


class PSNClient:
    """Thin wrapper around ``psnawp_api`` for fetching the caller's own library."""

    def __init__(self, npsso: str) -> None:
        if not npsso or not npsso.strip():
            raise PSNAuthenticationError(
                "No npsso token provided. Pass --npsso or set the PSN_NPSSO "
                "environment variable."
            )
        try:
            psnawp = PSNAWP(npsso.strip())
            self._client = psnawp.me()
        except PSNAWPInvalidTokenError as exc:
            raise PSNAuthenticationError(
                "The npsso token could not be parsed. Make sure you copied the "
                "full 64-character value with no extra whitespace."
            ) from exc
        except PSNAWPAuthenticationError as exc:
            raise PSNAuthenticationError(
                "PSN rejected the npsso token - it is likely expired or invalid. "
                f"Generate a fresh one by logging in to My PlayStation and visiting "
                f"{NPSSO_HELP_URL}"
            ) from exc

    @retry_with_backoff()
    def _fetch_title_stats(self, on_item: Optional[Callable[[int], None]] = None) -> List[Any]:
        return _collect(self._client.title_stats(), on_item)

    @retry_with_backoff()
    def _fetch_trophy_titles(self, on_item: Optional[Callable[[int], None]] = None) -> List[Any]:
        return _collect(self._client.trophy_titles(), on_item)

    def fetch_library(
        self,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> List[GameRecord]:
        """Fetch the full game library, merged with platinum trophy data.

        :param progress_callback: Optional callback invoked as
            ``progress_callback(stage, fetched_count)`` after each item is
            fetched from PSN, where ``stage`` is ``"titles"`` or ``"trophies"``.
            The total is not known up front, as PSN paginates both lists.
        """

        def reporter(stage: str) -> Optional[Callable[[int], None]]:
            if progress_callback is None:
                return None
            return lambda count: progress_callback(stage, count)

        try:
            titles = self._fetch_title_stats(reporter("titles"))
            trophy_titles = self._fetch_trophy_titles(reporter("trophies"))
        except PSNAWPAuthenticationError as exc:
            raise PSNAuthenticationError(
                "PSN authentication failed while fetching data - the npsso "
                "token likely expired mid-run. Generate a fresh token and retry."
            ) from exc

        # The same name can appear several times (e.g. PS4 and PS5 trophy
        # lists); a platinum earned in any of them counts.
        platinum_by_name: Dict[str, bool] = {}
        for trophy_title in trophy_titles:
            if not trophy_title.title_name:
                continue
            key = normalize_title_name(trophy_title.title_name)
            platinum_by_name[key] = platinum_by_name.get(key, False) or has_platinum(
                trophy_title.earned_trophies
            )

        records: List[GameRecord] = []
        for title in titles:
            name = title.name or ""
            records.append(
                GameRecord(
                    title=name,
                    platform=map_platform(title.category),
                    hours=hours_from_duration(title.play_duration),
                    completed_at=format_completed_at(title.last_played_date_time),
                    platinum=platinum_by_name.get(normalize_title_name(name), False),
                )
            )

        return records
