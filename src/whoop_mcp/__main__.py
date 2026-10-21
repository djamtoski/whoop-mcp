"""CLI: python -m whoop_mcp {login|serve|dashboard|status}"""

from __future__ import annotations

import argparse
import logging
import sys

from . import config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="whoop_mcp", description="WHOOP MCP server + dashboard")
    sub = parser.add_subparsers(dest="cmd")
    p_login = sub.add_parser("login", help="Authorize with WHOOP in the browser and cache tokens")
    p_login.add_argument("--no-browser", action="store_true", help="Print the URL instead of opening it")
    p_serve = sub.add_parser("serve", help="Run the MCP server over stdio (default)")
    p_serve.add_argument("--no-dashboard", action="store_true", help="Don't auto-start the web dashboard")
    p_dash = sub.add_parser("dashboard", help="Run only the web dashboard")
    p_dash.add_argument("--reload", action="store_true", help="Restart the dashboard when its Python code changes")
    p_dash.add_argument("--parent-pid", type=int, help=argparse.SUPPRESS)
    sub.add_parser("status", help="Show token/config status")
    p_export = sub.add_parser("export", help="Export your full WHOOP history (JSON + CSV)")
    p_export.add_argument("--out", help="Output root folder (default: ./exports)")
    p_import = sub.add_parser("import-app-export", help="Add the WHOOP app's Data Export ZIP to the latest export")
    p_import.add_argument("zip", help="Path to the ZIP emailed by WHOOP")
    args = parser.parse_args(argv)

    # stdout is the MCP transport — all logging must go to stderr.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    if args.cmd == "login":
        from .auth import AuthError, login

        try:
            path = login(open_browser=not args.no_browser)
        except (AuthError, RuntimeError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print(f"OK - WHOOP tokens saved to {path}")
        return 0

    if args.cmd == "dashboard":
        from . import dashboard

        print(f"Dashboard: http://localhost:{config.PORT}  (demo data: http://localhost:{config.PORT}/?demo=1)",
              file=sys.stderr)
        if args.reload:
            import os

            from .reloader import supervise

            child = [sys.executable, "-m", "whoop_mcp", "dashboard", "--parent-pid", str(os.getpid())]
            return supervise(child, parent_pid=args.parent_pid)
        if args.parent_pid:
            from .reloader import exit_with_parent

            exit_with_parent(args.parent_pid)
        dashboard.run()
        return 0

    if args.cmd == "export":
        import asyncio
        from pathlib import Path

        from .auth import AuthError
        from .export import export_history

        try:
            m = asyncio.run(export_history(Path(args.out) if args.out else None))
        except (AuthError, RuntimeError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print(f"\nExported to {m['directory']}")
        for k, n in m["counts"].items():
            span = m["date_range"].get(k) or [None, None]
            print(f"  {k:<11} {n:>6} records  {span[0]} -> {span[1]}")
        print(f"  months     {len(m['monthly_summary']):>6}")
        return 0

    if args.cmd == "import-app-export":
        from pathlib import Path

        from .export import import_app_export

        res = import_app_export(Path(args.zip))
        print(f"Extracted to {res['directory']}")
        for name, info in res["files"].items():
            print(f"  {name:<32} {info['rows']:>6} rows")
        return 0

    if args.cmd == "status":
        import time

        from .auth import load_tokens

        tok = load_tokens()
        print(f"Token file : {config.TOKEN_FILE} ({'present' if tok else 'missing'})")
        if tok:
            mins = (tok.get('expires_at', 0) - time.time()) / 60
            print(f"Access token expires in {mins:.0f} min; refresh token {'present' if tok.get('refresh_token') else 'MISSING'}")
        print(f"Redirect URI: {config.REDIRECT_URI}")
        return 0

    # default: serve
    from . import dashboard
    from .server import mcp

    if not getattr(args, "no_dashboard", False):
        started = dashboard.start_reloading_subprocess()
        logging.getLogger("whoop_mcp").warning(
            "Dashboard %s at http://localhost:%s", "started" if started else "already running", config.PORT)
    mcp.run(show_banner=False) if _supports_banner(mcp) else mcp.run()
    return 0


def _supports_banner(mcp) -> bool:
    import inspect

    try:
        return "show_banner" in inspect.signature(mcp.run).parameters
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    sys.exit(main())
