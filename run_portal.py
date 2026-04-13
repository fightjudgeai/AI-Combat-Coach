#!/usr/bin/env python3
"""
run_portal.py — Launch the AI Combat Coach portal.

Usage:
    python run_portal.py                  # default: localhost:8000
    python run_portal.py --port 3000
    python run_portal.py --host 0.0.0.0  # expose externally

Required env vars:
    SUPABASE_URL             — your Supabase project URL
    SUPABASE_SERVICE_KEY     — service role key (or SUPABASE_SERVICE_ROLE_KEY)
"""

import argparse
import os
import sys

def main() -> None:
    parser = argparse.ArgumentParser(description="AI Combat Coach Portal")
    parser.add_argument("--host",   default="127.0.0.1")
    parser.add_argument("--port",   default=8000, type=int)
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev)")
    args = parser.parse_args()

    # Soft-warn about missing DB config so the portal still starts
    if not (os.environ.get("SUPABASE_URL") and (
        os.environ.get("SUPABASE_SERVICE_KEY") or
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    )):
        print(
            "\n⚠  Warning: SUPABASE_URL / SUPABASE_SERVICE_KEY not set.\n"
            "   The portal will start but all DB queries will return empty.\n"
            "   Set the env vars and restart to connect to your Supabase project.\n",
            file=sys.stderr,
        )

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. Run: pip install uvicorn[standard]", file=sys.stderr)
        sys.exit(1)

    print(f"\n  AI Combat Coach Portal")
    print(f"  ─────────────────────────────────────────")
    print(f"  Local:   http://{args.host}:{args.port}")
    print(f"  DB:      {'✓ connected' if os.environ.get('SUPABASE_URL') else '✗ not configured'}\n")

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
