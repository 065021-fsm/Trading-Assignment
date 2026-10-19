# STARTER FILE (from lab) - MCP client: place a PAPER-trading SELL order via the Alpaca trading MCP server.
# Last amended: 24th Sep, 2026 (original). Paths made relative.
#
# Usage:   python sell_order_client_starter.py TSLA 2
# Requires: pip install fastmcp

import asyncio
import sys
import os
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

# Original used /home/ashok/crewai_pjt/mcp_servers/alpaca/servers/alpaca_trading_mcpServer.py
SERVER_SCRIPT = str(Path(__file__).parent / "servers" / "alpaca_trading_mcpServer.py")

# fastmcp's stdio transport forwards only a restricted "safe" set of env vars, so pass the
# full parent environment so ALPACA_API_KEY / ALPACA_SECRET_KEY reach the server subprocess.
transport = PythonStdioTransport(SERVER_SCRIPT, env=os.environ.copy())


async def place_sell_order(symbol: str, qty: float) -> None:
    async with Client(transport) as client:
        # Sanity check: show current position before selling
        position = await client.call_tool("get_position", {"symbol": symbol})
        print("Current position:", position.data)

        # An unfilled opposite-side open order (e.g. a pending BUY) makes Alpaca reject
        # the SELL as a potential wash trade, so check first.
        open_orders = await client.call_tool("get_open_orders", {"symbol": symbol})
        print("Open orders for", symbol, ":", open_orders.data)

        if open_orders.data.get("count", 0) > 0:
            print(f"\nWarning: {open_orders.data['count']} open order(s) exist for {symbol}.")
            print("Selling now may be rejected as a potential wash trade.")
            cancel = input("Cancel these open orders first? [y/N]: ").strip().lower()
            if cancel == "y":
                cancel_result = await client.call_tool("cancel_all_orders", {"symbol": symbol})
                print("Cancelled:", cancel_result.data)

        confirm = input(f"Confirm SELL {qty} share(s) of {symbol}? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Order cancelled.")
            return

        result = await client.call_tool("sell_stock", {"symbol": symbol, "qty": qty})
        print("Order result:", result.data)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python sell_order_client_starter.py <SYMBOL> <QTY>")
        sys.exit(1)
    asyncio.run(place_sell_order(sys.argv[1].upper(), float(sys.argv[2])))
