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
# Option A — Supabase Management API
# ---------------------------------------------------------------------------
def apply_via_management_api(sql: str, ref: str, token: str) -> None:
    try:
        import httpx  # type: ignore[import]
    except ImportError:
        sys.exit("httpx not installed — run: pip install httpx")

    url     = f"{SUPABASE_API_BASE}/projects/{ref}/database/query"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp    = httpx.post(url, headers=headers, json={"query": sql}, timeout=30)

    if resp.status_code not in (200, 201):
        sys.exit(f"  API error {resp.status_code}: {resp.text[:400]}")

    print("  ✓ Applied via Supabase Management API")


# ---------------------------------------------------------------------------
# Option B — direct psycopg3 connection
# ---------------------------------------------------------------------------
def apply_via_psycopg3(sql: str, db_url: str) -> None:
    try:
        import psycopg  # type: ignore[import]
    except ImportError:
        sys.exit("psycopg not installed — run: pip install 'psycopg[binary]'")

    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(sql)
    print("  ✓ Applied via direct psycopg3 connection")


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

        print(f"─── {name} ───")

        if dry_run:
            print(sql[:500] + (" …(truncated)" if len(sql) > 500 else ""))
            print("  [DRY RUN — not executing]")
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
        print("No migrations specified — defaulting to 006 and 007\n")

    run(targets, dry_run=args.dry_run)


if __name__ == "__main__":
    main()


Apply one or more SQL migrations to the Supabase database.

STRATEGY
--------
Supabase PostgREST doesn't expose a raw SQL endpoint. Two options:

  Option A — Direct psycopg2 connection (needs postgres password)
  Option B — Fly.io exec via flyctl (uses DATABASE_URL already in the backend)

This script implements both and auto-selects based on available credentials.

USAGE
-----
# Apply specific migration(s):
python tasks/apply_migrations.py 006 007

# Apply all unapplied migrations (sorted by number):
python tasks/apply_migrations.py --all

# Dry-run: print SQL without executing
python tasks/apply_migrations.py --dry-run 006 007

ENVIRONMENT VARIABLES (Option A — direct connection)
------------------------------------------------------
  SUPABASE_DB_URL   postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres
  
  If SUPABASE_DB_URL is not set, the script falls back to Option B.

OPTION B — FLY EXEC (no postgres password needed)
--------------------------------------------------
Requires flyctl in PATH and an authenticated fly token.
The fjai-backend app has DATABASE_URL set as a secret.
The script SSH-execs a python one-liner that reads DATABASE_URL
and passes the SQL to psycopg2.

  flyctl ssh console -a fjai-backend -C "python -c ..."
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT      = Path(__file__).resolve().parent.parent  # AI-Combat-Coach/
MIGRATIONS_DIR = REPO_ROOT / "migrations"
FLY_APP        = "fjai-backend"

# Project-specific — update if project changes
SUPABASE_PROJECT_REF = "cxvtipiogkgpqiksakld"


# ---------------------------------------------------------------------------
# Migration discovery
# ---------------------------------------------------------------------------
def list_migrations() -> list[Path]:
    """Return migration files sorted by their 3-digit prefix number."""
    files = sorted(
        MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"),
        key=lambda p: int(p.name[:3]),
    )
    return files


def get_migration(target: str) -> Path:
    """Resolve a migration by 3-digit number, e.g. '006'."""
    num = target.zfill(3)
    matches = list(MIGRATIONS_DIR.glob(f"{num}_*.sql"))
    if not matches:
        raise FileNotFoundError(
            f"No migration file found matching {num}_*.sql in {MIGRATIONS_DIR}"
        )
    return matches[0]


# ---------------------------------------------------------------------------
# Option A — direct psycopg2
# ---------------------------------------------------------------------------
def apply_via_psycopg2(sql: str, db_url: str) -> None:
    try:
        import psycopg2  # type: ignore[import]
    except ImportError:
        sys.exit("psycopg2 not installed — run: pip install psycopg2-binary")

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute(sql)
        print("  ✓ Applied via direct psycopg2 connection")
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Option B — Fly exec
# ---------------------------------------------------------------------------
def _escape_sql_for_shell(sql: str) -> str:
    """Escape SQL string for embedding in a single-quoted shell argument."""
    # Replace single-quotes with '\''
    return sql.replace("'", "'\\''")


def apply_via_fly(sql: str, app: str = FLY_APP) -> None:
    """
    SSH into the Fly.io app and execute SQL using the DATABASE_URL secret
    that's already injected into the backend container environment.

    The SQL is base64-encoded before being passed to the shell so newlines,
    single-quotes, and other special characters don't break the one-liner.
    """
    import base64
    b64_sql = base64.b64encode(sql.encode("utf-8")).decode("ascii")

    # The python one-liner decodes the b64 blob and executes it via psycopg2
    # Backend uses psycopg v3 (psycopg[binary]>=3.1.0), not psycopg2
    python_cmd = (
        "import os, base64, psycopg; "
        f"sql = base64.b64decode('{b64_sql}').decode(); "
        "conn = psycopg.connect(os.environ['DATABASE_URL'], autocommit=True); "
        "conn.execute(sql); "
        "conn.close(); "
        "print('Migration applied.')"
    )

    cmd = [
        "flyctl", "ssh", "console",
        "--app", app,
        "--command", f"python -c \"{python_cmd}\"",
    ]

    print(f"  Running: flyctl ssh console --app {app} --command python -c ...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("  STDERR:", result.stderr.strip())
        sys.exit(f"flyctl exec failed with code {result.returncode}")

    print("  STDOUT:", result.stdout.strip())
    print("  ✓ Applied via Fly.io exec")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(targets: list[str], dry_run: bool = False) -> None:
    # Resolve migration files
    if targets == ["--all"]:
        sql_files = list_migrations()
    else:
        sql_files = [get_migration(t) for t in targets]

    if not sql_files:
        print("No migrations to apply.")
        return

    # Choose strategy
    db_url   = os.environ.get("SUPABASE_DB_URL")
    strategy = "psycopg2" if db_url else "fly"

    print(f"Strategy: {'psycopg2 (direct)' if strategy == 'psycopg2' else 'Fly.io exec'}")
    print(f"Migrations to apply: {[f.name for f in sql_files]}\n")

    for path in sql_files:
        sql  = path.read_text(encoding="utf-8")
        name = path.name

        print(f"─── {name} ───")

        if dry_run:
            print(sql[:400] + (" …(truncated)" if len(sql) > 400 else ""))
            print("  [DRY RUN — not executing]")
            continue

        if strategy == "psycopg2":
            apply_via_psycopg2(sql, db_url)  # type: ignore[arg-type]
        else:
            apply_via_fly(sql)

        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply SQL migrations to Supabase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "migrations",
        nargs="*",
        metavar="NNN",
        help="Migration numbers to apply, e.g. 006 007. Omit to apply --all.",
    )
    parser.add_argument("--all",     action="store_true", help="Apply all migrations")
    parser.add_argument("--dry-run", action="store_true", help="Print SQL without executing")
    parser.add_argument("--list",    action="store_true", help="List available migrations and exit")

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
        # Default: apply 006 and 007
        targets = ["006", "007"]
        print("No migrations specified — defaulting to 006 and 007\n")

    run(targets, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
