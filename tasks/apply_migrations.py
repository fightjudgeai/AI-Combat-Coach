#!/usr/bin/env python3
"""
tasks/apply_migrations.py

Apply one or more SQL migrations to the Supabase database.

STRATEGY
--------
Uses the Supabase Management API (api.supabase.com) with the access token
stored by the Supabase CLI in Windows Credential Manager.

Falls back to direct psycopg2/psycopg connection if SUPABASE_DB_URL is set.

USAGE
-----
# Apply specific migration(s):
python tasks/apply_migrations.py 006 007

# Apply all migrations (sorted by number):
python tasks/apply_migrations.py --all

# Dry-run: print SQL without executing
python tasks/apply_migrations.py --dry-run 006 007

# List available migration files:
python tasks/apply_migrations.py --list

ENVIRONMENT VARIABLES (fallback to direct psycopg3 connection)
--------------------------------------------------------------
  SUPABASE_DB_URL   postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT      = Path(__file__).resolve().parent.parent  # AI-Combat-Coach/
MIGRATIONS_DIR = REPO_ROOT / "migrations"

SUPABASE_PROJECT_REF = "cxvtipiogkgpqiksakld"
SUPABASE_API_BASE    = "https://api.supabase.com/v1"


# ---------------------------------------------------------------------------
# Migration discovery
# ---------------------------------------------------------------------------
def list_migrations() -> list[Path]:
    return sorted(
        MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"),
        key=lambda p: int(p.name[:3]),
    )


def get_migration(target: str) -> Path:
    num = target.zfill(3)
    matches = list(MIGRATIONS_DIR.glob(f"{num}_*.sql"))
    if not matches:
        raise FileNotFoundError(f"No migration file found matching {num}_*.sql")
    return matches[0]


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
class _CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wt.DWORD), ("Type", wt.DWORD), ("TargetName", wt.LPWSTR),
        ("Comment", wt.LPWSTR), ("LastWritten", wt.FILETIME),
        ("CredentialBlobSize", wt.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wt.DWORD), ("AttributeCount", wt.DWORD),
        ("Attributes", ctypes.c_void_p), ("TargetAlias", wt.LPWSTR),
        ("UserName", wt.LPWSTR),
    ]


def _read_windows_credential(target: str) -> str | None:
    """Read a credential string from Windows Credential Manager."""
    try:
        ptr = ctypes.c_void_p()
        ok = ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(ptr))
        if not ok:
            return None
        cred = ctypes.cast(ptr, ctypes.POINTER(_CREDENTIAL)).contents
        blob = bytes(
            cred.CredentialBlob[i] for i in range(cred.CredentialBlobSize)
        )
        ctypes.windll.advapi32.CredFree(ptr)
        return blob.decode("utf-8", errors="replace")
    except Exception:
        return None


def get_supabase_token() -> str | None:
    """
    Try to obtain a Supabase Management API access token.
    - On Windows: reads from Credential Manager (set by `supabase login`)
    - Fallback: SUPABASE_ACCESS_TOKEN env var
    """
    token = _read_windows_credential("Supabase CLI:supabase")
    if token:
        return token
    return os.environ.get("SUPABASE_ACCESS_TOKEN")


# ---------------------------------------------------------------------------
# Option A â€” Supabase Management API
# ---------------------------------------------------------------------------
def apply_via_management_api(sql: str, ref: str, token: str) -> None:
    try:
        import httpx  # type: ignore[import]
    except ImportError:
        sys.exit("httpx not installed â€” run: pip install httpx")

    url     = f"{SUPABASE_API_BASE}/projects/{ref}/database/query"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp    = httpx.post(url, headers=headers, json={"query": sql}, timeout=30)

    if resp.status_code not in (200, 201):
        sys.exit(f"  API error {resp.status_code}: {resp.text[:400]}")

    print("  âœ“ Applied via Supabase Management API")


# ---------------------------------------------------------------------------
# Option B â€” direct psycopg3 connection
# ---------------------------------------------------------------------------
def apply_via_psycopg3(sql: str, db_url: str) -> None:
    try:
        import psycopg  # type: ignore[import]
    except ImportError:
        sys.exit("psycopg not installed â€” run: pip install 'psycopg[binary]'")

    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(sql)
    print("  âœ“ Applied via direct psycopg3 connection")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(targets: list[str], dry_run: bool = False) -> None:
    if targets == ["--all"]:
        sql_files = list_migrations()
    else:
        sql_files = [get_migration(t) for t in targets]

    if not sql_files:
        print("No migrations to apply.")
        return

    # Choose strategy
    db_url   = os.environ.get("SUPABASE_DB_URL")
    if db_url:
        strategy = "psycopg3"
        print("Strategy: psycopg3 (direct connection via SUPABASE_DB_URL)")
    else:
        token = get_supabase_token()
        if not token:
            sys.exit(
                "No credentials found.\n"
                "Run `supabase login` or set SUPABASE_ACCESS_TOKEN or SUPABASE_DB_URL."
            )
        strategy = "management_api"
        print("Strategy: Supabase Management API")

    print(f"Migrations to apply: {[f.name for f in sql_files]}\n")

    for path in sql_files:
        sql  = path.read_text(encoding="utf-8")
        name = path.name

        print(f"â”€â”€â”€ {name} â”€â”€â”€")

        if dry_run:
            print(sql[:500] + (" â€¦(truncated)" if len(sql) > 500 else ""))
            print("  [DRY RUN â€” not executing]")
            continue

        if strategy == "management_api":
            apply_via_management_api(sql, SUPABASE_PROJECT_REF, token)  # type: ignore[possibly-undefined]
        else:
            apply_via_psycopg3(sql, db_url)  # type: ignore[arg-type]

        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply SQL migrations to Supabase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("migrations", nargs="*", metavar="NNN",
                        help="Migration numbers, e.g. 006 007")
    parser.add_argument("--all",     action="store_true", help="Apply all migrations")
    parser.add_argument("--dry-run", action="store_true", help="Print SQL without executing")
    parser.add_argument("--list",    action="store_true", help="List migration files and exit")

    args = parser.parse_args()

    if args.list:
        for f in list_migrations():
            print(f.name)
        return

    if args.all:
        targets = ["--all"]
    elif args.migrations:
        targets = args.migrations
    else:
        targets = ["006", "007"]
        print("No migrations specified â€” defaulting to 006 and 007\n")

    run(targets, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
