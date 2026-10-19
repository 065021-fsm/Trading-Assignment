import argparse
import json
import os
from pathlib import Path
from uuid import uuid4
from typing import Any

try:
    from fastmcp import FastMCP
except Exception:  # pragma: no cover
    class FastMCP:  # minimal fallback for local dev/testing
        def __init__(self, name):
            self.name = name
            self._tools = {}

        def tool(self, *args, **kwargs):
            def decorator(func):
                self._tools[func.__name__] = func
                return func
            return decorator

        def run(self, transport="stdio"):
            return self

mcp = FastMCP("alpaca_trading")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
except Exception:  # pragma: no cover
    pass


def _client(api_key: str | None = None, secret_key: str | None = None):
    paper_setting = os.environ.get("ALPACA_PAPER", "true").strip().lower()
    if paper_setting not in {"true", "1", "yes"}:
        raise RuntimeError("Live trading is disabled; set ALPACA_PAPER=true to use paper trading.")
    if api_key is not None or secret_key is not None:
        api_key = (api_key or "").strip()
        secret_key = (secret_key or "").strip()
    else:
        if (
        os.environ.get("DASHBOARD_PAPER_CREDENTIALS_ONLY") == "true"
        and os.environ.get("DASHBOARD_PAPER_CREDENTIALS_CONFIGURED") != "true"
        ):
            raise RuntimeError("Connect an Alpaca paper account using the dashboard form.")
        api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        secret_key = os.environ.get("ALPACA_SECRET_KEY", "").strip()
    if not api_key or not secret_key:
        raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY are required for paper trading.")
    try:
        from alpaca.trading.client import TradingClient
    except ImportError as exc:
        raise RuntimeError("Install alpaca-py to connect to Alpaca paper trading.") from exc
    return TradingClient(api_key, secret_key, paper=True)


def verify_paper_credentials(api_key: str, secret_key: str) -> dict:
    api_key = api_key.strip()
    secret_key = secret_key.strip()
    if not api_key or not secret_key:
        raise ValueError("Enter both Alpaca paper API credentials.")
    try:
        account = get_account_for_credentials(api_key, secret_key)
    except Exception as exc:
        raise RuntimeError("Could not connect to this Alpaca paper account; verify the keys and network.") from exc
    return {"connected": True, "status": account["status"], "mode": "paper", "equity": account["equity"], "cash": account["cash"]}


def _serialize_order(order):
    return {
        "id": str(order.id),
        "symbol": order.symbol,
        "side": str(getattr(order.side, "value", order.side)).lower(),
        "qty": str(order.qty),
        "filled_qty": str(getattr(order, "filled_qty", 0) or 0),
        "filled_avg_price": str(getattr(order, "filled_avg_price", None) or ""),
        "status": str(getattr(order.status, "value", order.status)).lower(),
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        "client_order_id": order.client_order_id,
    }


def _submit_market_order(symbol: str, qty: float, side: str, portfolio: str = "shared"):
    if qty <= 0:
        raise ValueError("Order quantity must be greater than zero.")
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    safe_portfolio = portfolio.lower().replace("_", "-")[:16]
    order_data = MarketOrderRequest(
        symbol=symbol.upper(),
        qty=qty,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
        client_order_id=f"{safe_portfolio}-{symbol.upper()}-{uuid4().hex[:12]}",
    )
    order = _client().submit_order(order_data=order_data)
    return {"ok": True, "mode": "paper", "order": _serialize_order(order)}


def submit_paper_order_for_credentials(api_key: str, secret_key: str, symbol: str, qty: float, portfolio: str, action: str = "BUY"):
    if qty <= 0:
        raise ValueError("Order quantity must be greater than zero.")
    if portfolio not in {"bhavya_goel", "bhavya_gupta", "manya_arora"}:
        raise ValueError("Unknown student portfolio.")
    action = action.upper()
    if action not in {"BUY", "SELL"}:
        raise ValueError("Order action must be BUY or SELL.")
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    order = _client(api_key, secret_key).submit_order(order_data=MarketOrderRequest(
        symbol=symbol.upper(),
        qty=qty,
        side=OrderSide.BUY if action == "BUY" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
        client_order_id=f"{portfolio.replace('_', '-')}-{action.lower()}-{symbol.upper()}-{uuid4().hex[:12]}",
    ))
    return {"ok": True, "mode": "paper", "order": _serialize_order(order)}


@mcp.tool()
def get_account():
    return _account_payload(_client())


def _account_payload(client):
    account = client.get_account()
    return {
        "equity": float(account.equity),
        "last_equity": float(account.last_equity or account.equity),
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "status": str(account.status),
        "source": "alpaca-paper",
    }


def get_account_for_credentials(api_key: str, secret_key: str):
    return _account_payload(_client(api_key, secret_key))


@mcp.tool()
def get_position(symbol: str):
    client = _client()
    try:
        position = client.get_open_position(symbol.upper())
    except Exception as exc:
        if getattr(exc, "status_code", None) == 404:
            return {"symbol": symbol.upper(), "qty": 0, "market_value": 0.0}
        raise
    return {
        "symbol": position.symbol,
        "qty": float(position.qty),
        "market_value": float(position.market_value),
        "avg_entry_price": float(position.avg_entry_price),
    }


@mcp.tool()
def get_open_orders(symbol: str | None = None):
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    orders = _client().get_orders(filter=GetOrdersRequest(
        status=QueryOrderStatus.OPEN,
        symbols=[symbol.upper()] if symbol else None,
    ))
    return {"count": len(orders), "orders": [_serialize_order(order) for order in orders]}


@mcp.tool()
def cancel_all_orders(symbol: str | None = None):
    client = _client()
    orders = client.get_orders()
    cancelled = []
    for order in orders:
        if symbol is None or order.symbol == symbol.upper():
            client.cancel_order_by_id(order.id)
            cancelled.append(str(order.id))
    return {"cancelled": cancelled, "count": len(cancelled), "mode": "paper"}


@mcp.tool()
def sell_stock(symbol: str, qty: float):
    return _submit_market_order(symbol, float(qty), "sell")


@mcp.tool()
def buy_stock(symbol: str, qty: float | None = None, notional: float | None = None, portfolio: str = "shared"):
    qty_value = qty if qty is not None else float((notional or 0.0) / 100.0)
    return _submit_market_order(symbol, float(qty_value), "buy", portfolio=portfolio)


@mcp.tool()
def get_positions():
    return _positions_payload(_client())


def _positions_payload(client):
    positions = client.get_all_positions()
    return {
        position.symbol: {
            "symbol": position.symbol,
            "qty": float(position.qty),
            "market_value": float(position.market_value),
            "avg_entry_price": float(position.avg_entry_price),
            "current_price": float(position.current_price or 0),
            "unrealized_pl": float(position.unrealized_pl or 0),
            "unrealized_plpc": float(position.unrealized_plpc or 0),
            "unrealized_intraday_pl": float(position.unrealized_intraday_pl or 0),
        }
        for position in positions
    }


def get_positions_for_credentials(api_key: str, secret_key: str):
    return _positions_payload(_client(api_key, secret_key))


def get_open_orders_for_credentials(api_key: str, secret_key: str):
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    orders = _client(api_key, secret_key).get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
    return [_serialize_order(order) for order in orders]


def get_recent_orders_for_credentials(api_key: str, secret_key: str, limit: int = 100):
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    orders = _client(api_key, secret_key).get_orders(filter=GetOrdersRequest(
        status=QueryOrderStatus.ALL,
        limit=limit,
    ))
    serialized = [_serialize_order(order) for order in orders]
    return sorted(serialized, key=lambda order: order["submitted_at"] or "", reverse=True)


@mcp.tool()
def get_portfolio(portfolio: str = "shared"):
    account = get_account()
    return {"portfolio": portfolio, "cash": account["cash"], "positions": get_positions(), "equity": account["equity"]}

def _probe(tool_name: str, symbol: str, qty: float, portfolio: str = "shared"):
    if tool_name == "get_account":
        return get_account()
    if tool_name == "get_position":
        return get_position(symbol)
    if tool_name == "sell_stock":
        return sell_stock(symbol, qty)
    if tool_name == "buy_stock":
        return buy_stock(symbol, qty, portfolio=portfolio)
    return {"error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alpaca trading MCP server (simple fallback mode)")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--tool", choices=["get_account", "get_position", "sell_stock", "buy_stock"], default="get_account")
    parser.add_argument("--symbol", default="TSLA")
    parser.add_argument("--qty", type=float, default=1.0)
    parser.add_argument("--portfolio", default="shared")
    args = parser.parse_args()

    if args.probe:
        print(json.dumps(_probe(args.tool, args.symbol, args.qty, args.portfolio), indent=2))
        raise SystemExit(0)

    mcp.run(transport="stdio")
