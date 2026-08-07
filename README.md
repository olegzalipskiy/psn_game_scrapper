# psn_game_scrapper

[![Tests](https://github.com/olegzalipskiy/psn_game_scrapper/actions/workflows/tests.yml/badge.svg)](https://github.com/olegzalipskiy/psn_game_scrapper/actions/workflows/tests.yml)

Export your PlayStation Network (PSN) game library — titles, platform, hours
played, last-played date, and platinum status — to a CSV file ready to import
into [GRAVK](https://gravk.app).

Built on the unofficial [`psnawp`](https://pypi.org/project/psnawp/) library
(import name `psnawp_api`), which talks to the same private PSN endpoints the
PlayStation App uses. There is no official PSN API, so this relies on the
`npsso` session cookie from your PSN account.

## How it works

1. Authenticates to PSN using your `npsso` token.
2. Fetches your title stats (`client.title_stats()`) — name, platform,
   total play duration, last-played date.
3. Fetches your trophy summaries (`client.trophy_titles()`) — used only to
   determine whether each title has a platinum trophy.
4. Merges the two by (normalized) title name and writes one CSV row per game.

## Installation

### pip / pipx

```bash
pip install psn-game-scrapper
# or, isolated from your other Python packages:
pipx install psn-game-scrapper
```

This installs a `psn-export` command on your `PATH`. Requires Python 3.9+.

Not published to PyPI yet? Install straight from GitHub:

```bash
pipx install git+https://github.com/olegzalipskiy/psn_game_scrapper.git
```

### Homebrew

```bash
brew tap olegzalipskiy/psn_game_scrapper https://github.com/olegzalipskiy/psn_game_scrapper
brew install psn-game-scrapper
```

This also installs the `psn-export` command. See [Formula/psn-game-scrapper.rb](Formula/psn-game-scrapper.rb).

### From source (for development)

```bash
git clone https://github.com/olegzalipskiy/psn_game_scrapper.git
cd psn_game_scrapper
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

## Getting your npsso token

1. Log in to [My PlayStation](https://my.playstation.com) in your browser.
2. While still logged in, visit
   `https://ca.account.sony.com/api/v1/ssocookie`.
3. The page returns JSON like `{"npsso": "64-character-string"}`. Copy the
   64-character value — that's your token.
4. The token expires after about 2 months (or immediately if you log out of
   PSN in that browser), so you may need to repeat this step later.

Keep this token secret — it grants access to your PSN account.

## Usage

```bash
# Pass the token directly
psn-export --npsso <your-64-char-npsso-token> --output games.csv

# Or set it as an environment variable
export PSN_NPSSO=<your-64-char-npsso-token>
psn-export --output games.csv

# Only export games with at least 1 hour of playtime
psn-export --output games.csv --min-hours 1

# Omit --output to get the default name: psn_library_export_{YYYY-MM-DD}.csv
psn-export
```

Running from a source checkout without installing the console script also
works: `python -m psn_game_scrapper` (same flags).

### CLI options

| Flag          | Required | Default                                    | Description                                   |
|---------------|----------|---------------------------------------------|------------------------------------------------|
| `--npsso`     | No*      | `$PSN_NPSSO` environment variable           | PSN npsso token                                 |
| `--output`    | No       | `psn_library_export_{YYYY-MM-DD}.csv`       | Output CSV file path                            |
| `--min-hours` | No       | `0` (export everything)                     | Only include games with at least this many hours |

\* Either `--npsso` or `PSN_NPSSO` must be set; the script exits with an
error message otherwise.

## Output CSV format

Matches the GRAVK import template exactly (`title,hours,completedAt,platform,
status,userScore,platinum,steamDeck,favorite`):

- UTF-8 encoded, comma-separated, one header row followed by one row per game.
- Empty/unknown optional fields are written as an empty string, never the
  text `None` or `null`.

| Column       | Source                                                                  | Notes |
|--------------|--------------------------------------------------------------------------|-------|
| `title`      | `title_stats().name`                                                     | Required field |
| `hours`      | `title_stats().play_duration`                                            | Rounded to the nearest whole hour |
| `completedAt`| `title_stats().last_played_date_time`                                    | Date of the most recent play session (`YYYY-MM-DD`), empty if PSN has no record of it |
| `platform`   | `title_stats().category`                                                 | `PS4`/`PS5` are both mapped to `PlayStation`; anything else passes through unchanged |
| `status`     | —                                                                        | Always empty — left for GRAVK to auto-detect from hours played, per the GRAVK template's own rule |
| `userScore`  | —                                                                        | Always empty — PSN has no such field |
| `platinum`   | `trophy_titles().earned_trophies.platinum`, matched by normalized name    | `true`/`false` |
| `steamDeck`  | —                                                                        | Always `false` — PSN games are never played on Steam Deck |
| `favorite`   | —                                                                        | Always empty — left as a GRAVK default |

Note: GRAVK's own `review` field is not part of the import template, so this
exporter does not produce one either.

## Known limitation

Title matching between the "titles you've played" endpoint and the "trophy
summaries" endpoint is done by normalizing and comparing title names (case,
whitespace, `™`/`®` symbols). PSN does not expose one shared ID between these
two endpoints for a user's whole library. In the rare case a game's name
differs meaningfully between the two responses, `platinum` will read `false`
for that title even if a platinum was actually earned. Everything else
(`title`, `hours`, `completedAt`, `platform`) is unaffected, since it
comes entirely from `title_stats()`.

## Project layout

```
src/psn_game_scrapper/
    client.py       # PSNAWP wrapper: auth, fetching, retry/backoff, data mapping
    csv_writer.py   # CSV formatting/writing, min-hours filtering
    cli.py          # CLI entry point (the `psn-export` console script)
Formula/            # Homebrew formula
tests/               # pytest suite (fully mocked, no network/token required)
```

## Running the tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

The suite mocks every PSN API call (`unittest.mock`/`pytest-mock`) — it
never hits the network and never needs a real npsso token. It covers:

- platform mapping (PS4/PS5 → `PlayStation`, unknown platforms pass through)
- rounding play duration to whole hours
- platinum detection from trophy data
- CSV header names/order and empty-vs-`None` formatting
- the `--min-hours` filter
- invalid/expired npsso token handling
- exponential-backoff retry behavior on simulated rate-limit (429) errors

To check coverage locally the same way CI does:

```bash
pytest tests/ --cov=psn_game_scrapper --cov-report=term-missing --cov-fail-under=80
```

## Continuous integration

Every pull request targeting `master` runs the test suite via
[GitHub Actions](.github/workflows/tests.yml) and posts a comment on the PR
with the pass/fail results and coverage report. The build fails — blocking
the merge — if any test fails or total coverage drops below **80%**. The
pipeline does not run on plain commits/pushes, only on pull requests into
`master`.

> **Note:** for the check to actually block merging, the repository's branch
> protection rule for `master` must have "Require status checks to pass
> before merging" enabled with the `Run tests (min 80% coverage)` check
> selected (Settings → Branches).

## Releasing (maintainers)

1. Bump `version` in `pyproject.toml` and `__version__` in
   `src/psn_game_scrapper/__init__.py`.
2. Tag the release: `git tag v0.1.0 && git push origin v0.1.0`. This
   triggers [`.github/workflows/publish.yml`](.github/workflows/publish.yml),
   which builds the package and publishes it to PyPI via
   [trusted publishing](https://docs.pypi.org/trusted-publishers/) — no
   API token needed, but the PyPI project must have a trusted publisher
   configured for this repo/workflow first (one-time setup on pypi.org).
3. Update [Formula/psn-game-scrapper.rb](Formula/psn-game-scrapper.rb):
   point `url` at the new tag's tarball and refresh `sha256` with
   `curl -sL <tarball-url> | shasum -a 256`. If any dependency version
   changed, refresh its `resource` block the same way (URL + sha256 from
   `https://pypi.org/pypi/<package>/<version>/json`).

## Troubleshooting

- **"The npsso token could not be parsed"** — you likely copied a truncated
  or malformed value. Re-fetch it from
  `https://ca.account.sony.com/api/v1/ssocookie` while logged in.
- **"PSN rejected the npsso token - it is likely expired or invalid"** —
  npsso tokens expire; generate a new one following the steps above.
- **Rate limiting** — the script automatically retries PSN rate-limit
  (429) and server errors with exponential backoff (up to 5 attempts by
  default); large libraries with hundreds of games may take a few minutes.
