import argparse
import json
from typing import Any

from dashboard import serve_dashboard
from mcp_servers.stock_trading.trading_crew import build_common_portfolio_view, build_trading_summary


def run_cli(args: dict[str, Any] | None = None) -> dict[str, Any]:
    options = {
        "portfolio": "bhavya_goel",
        "symbol": "TSLA",
        "dry_run": True,
    }
    if args:
        options.update(args)

    result = build_trading_summary(
        portfolio_name=str(options.get("portfolio", "bhavya_goel")),
        symbol=str(options.get("symbol", "TSLA")),
        dry_run=bool(options.get("dry_run", True)),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal trading summary CLI")
    parser.add_argument("--portfolio", default="bhavya_goel", help="Portfolio name to inspect")
    parser.add_argument("--symbol", default="TSLA", help="Ticker to analyze")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Use dry-run order execution mode")
    parser.add_argument("--paper", dest="dry_run", action="store_false", help="Submit a paper order if the current signal is BUY or SELL")
    parser.add_argument("--dashboard", action="store_true", help="Run the interactive browser dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard bind address")
    parser.add_argument("--port", type=int, default=8765, help="Dashboard port")
    parsed = parser.parse_args()

    if parsed.dashboard:
        serve_dashboard(host=parsed.host, port=parsed.port)
        return 0

    report = run_cli({
        "portfolio": parsed.portfolio,
        "symbol": parsed.symbol,
        "dry_run": parsed.dry_run,
    })
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
