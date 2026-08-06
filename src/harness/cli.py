"""``harness`` command-line entrypoint: ``harness serve`` and ``harness tui``.

Uses argparse (stdlib) to keep the dependency set minimal (AGENTS.md).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

from harness.core.config import HarnessConfig, load_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the Harness API server.")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--config", default=None, help="Path to a harness.yaml config file.")

    tui = sub.add_parser("tui", help="Run the Harness TUI client.")
    tui.add_argument("--api", default="http://127.0.0.1:4096", help="Harness API base URL.")
    tui.add_argument("--token", default=None, help="Bearer token for remote connections.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        server_overrides: dict[str, object] = {}
        if args.host is not None:
            server_overrides["host"] = args.host
        if args.port is not None:
            server_overrides["port"] = args.port
        config = load_config(
            config_file=Path(args.config) if args.config else None,
            overrides=({"server": server_overrides} if server_overrides else None),
        )
        _serve(config)
        return 0

    if args.command == "tui":
        from harness.tui.app import run_tui

        run_tui(api_base=args.api, token=args.token)
        return 0

    parser.print_help()
    return 1


def _serve(config: HarnessConfig) -> None:
    from harness.api.app import create_app

    app = create_app(config)
    uvicorn.run(app, host=config.server.host, port=config.server.port, log_level="info")


if __name__ == "__main__":
    sys.exit(main())
