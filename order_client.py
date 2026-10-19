import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SERVER_SCRIPT = Path(__file__).resolve().parent / "servers" / "alpaca_trading_mcpServer.py"


def parse_args():
    parser = argparse.ArgumentParser(description="Minimal Alpaca paper order client")
    parser.add_argument("symbol", help="Ticker to trade")
    parser.add_argument("qty", type=float, help="Quantity to buy or sell")
    parser.add_argument("--side", choices=["buy", "sell"], default="sell")
    parser.add_argument("--dry-run", action="store_true", help="Do not send a real order in the demo mode")
    parser.add_argument("--portfolio", default="shared")
    return parser.parse_args()


def probe_server(symbol: str, qty: float, side: str):
    cmd = [
        sys.executable,
        str(SERVER_SCRIPT),
        "--probe",
        "--tool",
        "sell_stock" if side == "sell" else "buy_stock",
        "--symbol",
        symbol,
        "--qty",
        str(qty),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy(), check=False)
    print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode


def main():
    args = parse_args()
    print(f"Demo order request: {args.side.upper()} {args.qty} {args.symbol.upper()} (dry_run={args.dry_run})")
    probe_server(args.symbol.upper(), args.qty, args.side)
    payload = {
        "symbol": args.symbol.upper(),
        "qty": args.qty,
        "side": args.side,
        "status": "demo-ok",
        "portfolio": args.portfolio,
        "dry_run": args.dry_run,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
