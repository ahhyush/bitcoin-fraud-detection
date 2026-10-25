"""Download competition data from Kaggle, and submit predictions.

Credentials come from .env (gitignored). Kaggle has two credential systems and
they are not interchangeable:

  * API token (preferred) — one opaque string like `abcd_<32 hex>`, from
    Settings -> API -> "Generate New Token". Goes in KAGGLE_API_TOKEN.
  * Legacy key — a username + 32-hex-key pair from a downloaded kaggle.json.
    Goes in KAGGLE_USERNAME + KAGGLE_KEY.

Either works; this script accepts both and prefers the token.

    python scripts/kaggle_data.py check          # verify credentials work
    python scripts/kaggle_data.py download       # fetch + unzip into data/raw/
    python scripts/kaggle_data.py submit FILE -m "message"

`KAGGLE_CONFIG_DIR` is pinned into the repo so the Kaggle client never writes
to ~/.kaggle (which is not writable in this sandbox).
"""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW = REPO_ROOT / "data" / "raw"


CREDENTIAL_HELP = """
Put ONE of these in .env (gitignored):

  API token (preferred) — Settings -> API -> "Generate New Token", then copy
  the whole string exactly as shown, including any prefix before the underscore:
    KAGGLE_API_TOKEN=abcd_0123456789abcdef0123456789abcdef

  Legacy key — "Create Legacy API Key" downloads a kaggle.json; copy both fields:
    KAGGLE_USERNAME=jsmith
    KAGGLE_KEY=0123456789abcdef0123456789abcdef

A bare KAGGLE=... line does not work; the client looks for the names above.
"""


def load_env() -> str:
    """Read .env into os.environ and report which credential style was found.

    Parsed manually rather than via python-dotenv so the error messages can
    name the specific missing variable.
    """
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            # Tolerate quoted values even though the project's .env has none.
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

    # Keep the Kaggle client out of ~/.kaggle, which the sandbox blocks.
    os.environ.setdefault("KAGGLE_CONFIG_DIR", str(REPO_ROOT / ".kaggle"))
    Path(os.environ["KAGGLE_CONFIG_DIR"]).mkdir(exist_ok=True)

    if os.environ.get("KAGGLE_API_TOKEN"):
        return "api_token"
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return "legacy_key"
    sys.exit(f"No Kaggle credentials found.\n{CREDENTIAL_HELP}")


def api():
    """Authenticate and return a Kaggle API client."""
    load_env()
    from kaggle.api.kaggle_api_extended import KaggleApi

    client = KaggleApi()
    client.authenticate()
    return client


def check() -> None:
    """Verify credentials against a real API call.

    `authenticate()` only reads local config and does not contact Kaggle, so it
    succeeds even with a bad credential; only an actual request proves it works.
    """
    style = load_env()
    try:
        client = api()
        client.competitions_list(search="bitcoin")
    except Exception as exc:  # noqa: BLE001 - surface the cause verbatim
        sys.exit(
            f"Kaggle rejected the {style} credential ({type(exc).__name__}: "
            f"{str(exc)[:160]})\n{CREDENTIAL_HELP}"
        )
    print(f"Credentials OK ({style}).")


def competition_slug() -> str:
    slug = os.environ.get("KAGGLE_COMPETITION", "").strip()
    if not slug:
        sys.exit(
            "Set KAGGLE_COMPETITION in .env to the slug from the competition URL,\n"
            "e.g. kaggle.com/competitions/foo-bar  ->  KAGGLE_COMPETITION=foo-bar"
        )
    return slug


def download() -> None:
    """Fetch the competition archive and unzip it into data/raw/."""
    client = api()
    slug = competition_slug()
    RAW.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {slug} -> {RAW}")
    try:
        client.competition_download_files(slug, path=str(RAW), quiet=False)
    except Exception as exc:  # noqa: BLE001
        sys.exit(
            f"Download failed: {exc}\n\n"
            "If this is a 403, open the competition page and accept its rules\n"
            "first — the API cannot download data until you have joined."
        )

    for archive in RAW.glob("*.zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(RAW)
        archive.unlink()
        print(f"unzipped {archive.name}")

    files = sorted(p for p in RAW.iterdir() if p.is_file() and p.name != ".gitkeep")
    print(f"\n{len(files)} file(s) in data/raw/:")
    for f in files:
        print(f"  {f.name:<28} {f.stat().st_size / 1e6:>8.1f} MB")


def submit(path: str, message: str) -> None:
    """Upload a submission CSV."""
    client = api()
    slug = competition_slug()
    csv = Path(path)
    if not csv.exists():
        sys.exit(f"No such file: {csv}")

    client.competition_submit(file_name=str(csv), message=message, competition=slug)
    print(f"Submitted {csv.name}: {message!r}")
    print("Remember: 3 submissions per day.")


if __name__ == "__main__":
    args = sys.argv[1:]
    command = args[0] if args else "check"

    if command == "check":
        check()
    elif command == "download":
        download()
    elif command == "submit":
        if not args[1:]:
            sys.exit("usage: submit FILE [-m MESSAGE]")
        msg = "submission"
        if "-m" in args:
            msg = args[args.index("-m") + 1]
        submit(args[1], msg)
    else:
        sys.exit(f"Unknown command {command!r}. Use: check | download | submit")
