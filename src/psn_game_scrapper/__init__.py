"""Export your PSN game library to a GRAVK-compatible CSV file."""

from importlib.metadata import PackageNotFoundError, version

from .client import GameRecord, PSNAuthenticationError, PSNClient
from .csv_writer import write_csv

try:
    __version__ = version("psn-game-scrapper")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "unknown"

__all__ = [
    "GameRecord",
    "PSNAuthenticationError",
    "PSNClient",
    "write_csv",
    "__version__",
]
