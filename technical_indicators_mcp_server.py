import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

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

mcp = FastMCP("technical_indicators")
PROJECT_ROOT = Path(__file__).resolve().parents[3]

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=False)
except Exception:  # pragma: no cover
    pass


def _get_mock_bars(symbol: str, lookback_days: int = 180, timeframe: str = "1Day"):
    end = pd.Timestamp.now(tz="UTC").floor("D")
    dates = pd.date_range(end=end, periods=lookback_days, freq="D")
    base = 100.0 if symbol != "TSLA" else 250.0
    drift = 0.008 if symbol != "TSLA" else 0.012
    prices = []
    last = base
    for i, day in enumerate(dates):
        last = last * (1 + (math.sin(i / 7.0) * 0.02) + drift * (0.5 if i % 2 == 0 else -0.3))
        o = last * (1 - 0.01)
        h = last * (1 + 0.015)
        l = last * (1 - 0.018)
        c = last
        v = 1000000 + (i * 12000)
        prices.append({
            "t": day.strftime("%Y-%m-%dT00:00:00Z"),
            "o": round(o, 4),
            "h": round(h, 4),
            "l": round(l, 4),
            "c": round(c, 4),
            "v": int(v),
        })
    return {"symbol": symbol, "timeframe": timeframe, "bars": prices, "bar_count": len(prices)}


def _get_alpaca_bars(symbol: str, lookback_days: int = 180, timeframe: str = "1Day"):
    return _get_alpaca_bars_multi([symbol], lookback_days, timeframe)[symbol.upper()]


def _get_alpaca_bars_multi(
    symbols: list[str],
    lookback_days: int = 180,
    timeframe: str = "1Day",
    api_key: str | None = None,
    secret_key: str | None = None,
):
    if api_key is None and (
        os.environ.get("DASHBOARD_PAPER_CREDENTIALS_ONLY") == "true"
        and os.environ.get("DASHBOARD_PAPER_CREDENTIALS_CONFIGURED") != "true"
    ):
        raise RuntimeError("Connect your Alpaca paper account using the dashboard form.")
    api_key = (api_key or os.environ.get("ALPACA_API_KEY", "")).strip()
    secret_key = (secret_key or os.environ.get("ALPACA_SECRET_KEY", "")).strip()
    if not api_key or not secret_key:
        raise RuntimeError("Live Alpaca market data requires ALPACA_API_KEY and ALPACA_SECRET_KEY.")
    if timeframe != "1Day":
        raise ValueError("Alpaca data currently supports the 1Day timeframe only.")

    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    feed_name = os.environ.get("ALPACA_DATA_FEED", "iex").strip().lower()
    if feed_name != "iex":
        raise ValueError("This paper-trading setup is restricted to Alpaca's IEX data feed.")
    client = StockHistoricalDataClient(api_key, secret_key)
    request = StockBarsRequest(
        symbol_or_symbols=[symbol.upper() for symbol in symbols],
        timeframe=TimeFrame.Day,
        start=datetime.now().astimezone() - timedelta(days=max(lookback_days * 2, lookback_days + 30)),
        end=datetime.now().astimezone(),
        feed=DataFeed.IEX,
    )
    frame = client.get_stock_bars(request).df
    if frame.empty:
        raise RuntimeError("Alpaca returned no IEX bars for the requested symbols.")

    result = {}
    for symbol in [item.upper() for item in symbols]:
        symbol_frame = frame
        if isinstance(frame.index, pd.MultiIndex):
            try:
                symbol_frame = frame.xs(symbol, level="symbol")
            except KeyError:
                raise RuntimeError(f"Alpaca returned no IEX bars for {symbol}.") from None
        elif len(symbols) != 1:
            raise RuntimeError("Alpaca returned an unexpected multi-symbol bars response.")
        symbol_frame = symbol_frame.reset_index()
        bars = []
        for row in symbol_frame.tail(lookback_days).to_dict(orient="records"):
            timestamp = row.get("timestamp")
            bars.append({
                "t": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
                "o": float(row["open"]),
                "h": float(row["high"]),
                "l": float(row["low"]),
                "c": float(row["close"]),
                "v": int(row["volume"]),
            })
        if not bars:
            raise RuntimeError(f"Alpaca returned no usable IEX bars for {symbol}.")
        result[symbol] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "bars": bars,
            "bar_count": len(bars),
            "source": "alpaca-iex",
        }
    return result


def _get_bars(symbol: str, lookback_days: int = 180, timeframe: str = "1Day"):
    provider = os.environ.get("MARKET_DATA_PROVIDER", "alpaca").strip().lower()
    if provider == "mock":
        return _get_mock_bars(symbol, lookback_days, timeframe)
    if provider != "alpaca":
        raise ValueError("MARKET_DATA_PROVIDER must be 'alpaca' or explicitly 'mock'.")
    return _get_alpaca_bars(symbol, lookback_days, timeframe)


def _rsi(series, period=14):
    if len(series) < period + 1:
        return None
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = (-delta.clip(upper=0))
    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_gain_last = float(avg_gain.iloc[-1])
    avg_loss_last = float(avg_loss.iloc[-1])

    if math.isclose(avg_loss_last, 0.0, abs_tol=1e-12):
        return 100.0 if avg_gain_last > 0 else 50.0

    rs = avg_gain_last / avg_loss_last
    return float(100 - (100 / (1 + rs)))


def _macd(series, fast=12, slow=26, signal=9):
    if len(series) < slow + signal:
        return None, None, None
    fast_ema = series.ewm(span=fast, adjust=False).mean()
    slow_ema = series.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(hist.iloc[-1])


@mcp.tool()
def fetch_ohlcv(symbol: str, lookback_days: int = 180, timeframe: str = "1Day"):
    """Return daily OHLCV bars from Alpaca IEX, or synthetic bars in explicit mock mode."""
    return _get_bars(symbol, lookback_days, timeframe)


@mcp.tool()
def fetch_ohlcv_multi(symbols: list[str], lookback_days: int = 180, timeframe: str = "1Day"):
    """Return daily OHLCV payloads for multiple symbols."""
    return _get_bars_multi(symbols, lookback_days, timeframe)


def _get_bars_multi(symbols: list[str], lookback_days: int = 180, timeframe: str = "1Day"):
    provider = os.environ.get("MARKET_DATA_PROVIDER", "alpaca").strip().lower()
    if provider == "mock":
        return {symbol.upper(): _get_mock_bars(symbol.upper(), lookback_days, timeframe) for symbol in symbols}
    if provider != "alpaca":
        raise ValueError("MARKET_DATA_PROVIDER must be 'alpaca' or explicitly 'mock'.")
    return _get_alpaca_bars_multi(symbols, lookback_days, timeframe)


@mcp.tool()
def calculate_rsi(symbol: str, period: int = 14, lookback_days: int = 180, timeframe: str = "1Day"):
    data = _get_bars(symbol, lookback_days, timeframe)
    closes = pd.Series([bar["c"] for bar in data["bars"]])
    rsi = _rsi(closes, period)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "rsi": round(rsi, 2) if rsi is not None else None,
        "close": closes.iloc[-1] if len(closes) else None,
        "as_of": data["bars"][-1]["t"] if data["bars"] else None,
        "signal": "Oversold" if rsi is not None and rsi < 30 else "Overbought" if rsi is not None and rsi > 70 else "Neutral",
    }


@mcp.tool()
def calculate_macd(symbol: str, fast: int = 12, slow: int = 26, signal: int = 9, lookback_days: int = 180, timeframe: str = "1Day"):
    data = _get_bars(symbol, lookback_days, timeframe)
    closes = pd.Series([bar["c"] for bar in data["bars"]])
    macd, sig, hist = _macd(closes, fast=fast, slow=slow, signal=signal)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "macd": round(macd, 4) if macd is not None else None,
        "signal": round(sig, 4) if sig is not None else None,
        "histogram": round(hist, 4) if hist is not None else None,
        "close": closes.iloc[-1] if len(closes) else None,
        "as_of": data["bars"][-1]["t"] if data["bars"] else None,
        "crossover": "Bullish" if (macd is not None and sig is not None and macd > sig) else "Bearish" if (macd is not None and sig is not None and macd < sig) else "None",
    }


@mcp.tool()
def get_market_clock():
    now = datetime.utcnow()
    return {"timestamp_utc": now.isoformat() + "Z", "session": "regular" if 9 <= now.hour < 16 else "closed"}


@mcp.tool()
def get_session():
    return {"session": "regular"}


@mcp.tool()
def compute_indicators_multi(symbols: list[str], indicators: list[str] | None = None):
    if indicators is None:
        indicators = ["rsi", "macd", "sma_50", "ema_20", "bollinger"]
    all_bars = _get_bars_multi(symbols, 180, "1Day")
    return _compute_indicators_from_bars(symbols, indicators, all_bars)


def compute_indicators_multi_for_credentials(
    symbols: list[str],
    indicators: list[str],
    api_key: str,
    secret_key: str,
):
    bars = _get_alpaca_bars_multi(symbols, 180, "1Day", api_key=api_key, secret_key=secret_key)
    return _compute_indicators_from_bars(symbols, indicators, bars)


def _compute_indicators_from_bars(symbols: list[str], indicators: list[str], all_bars: dict):
    payload = {}
    for symbol in symbols:
        data = all_bars[symbol.upper()]
        closes = pd.Series([bar["c"] for bar in data["bars"]])
        result = {"symbol": symbol}
        if "rsi" in indicators:
            result["rsi"] = _rsi(closes, 14)
        if "macd" in indicators:
            macd, sig, hist = _macd(closes, 12, 26, 9)
            result["macd"] = {"macd": macd, "signal": sig, "histogram": hist}
        if "sma_50" in indicators:
            average = float(closes.rolling(window=50, min_periods=50).mean().iloc[-1]) if len(closes) >= 50 else None
            close = float(closes.iloc[-1]) if len(closes) else None
            result["sma_50"] = {
                "average": average,
                "close": close,
                "signal": "BUY" if average is not None and close > average else "SELL" if average is not None and close < average else "HOLD",
            }
        if "ema_20" in indicators:
            average = float(closes.ewm(span=20, adjust=False, min_periods=20).mean().iloc[-1]) if len(closes) >= 20 else None
            close = float(closes.iloc[-1]) if len(closes) else None
            result["ema_20"] = {
                "average": average,
                "close": close,
                "signal": "BUY" if average is not None and close > average else "SELL" if average is not None and close < average else "HOLD",
            }
        if "bollinger" in indicators:
            if len(closes) >= 20:
                window = closes.tail(20)
                middle = float(window.mean())
                deviation = float(window.std(ddof=0))
                upper = middle + 2 * deviation
                lower = middle - 2 * deviation
                close = float(closes.iloc[-1])
                band_signal = "BUY" if close < lower else "SELL" if close > upper else "HOLD"
            else:
                upper = middle = lower = close = None
                band_signal = "HOLD"
            result["bollinger"] = {
                "upper": upper,
                "middle": middle,
                "lower": lower,
                "close": close,
                "signal": band_signal,
            }
        payload[symbol] = result
    return payload


def _probe(
    tool_name: str,
    symbol: str,
    lookback_days: int = 180,
    timeframe: str = "1Day",
    symbols: list[str] | None = None,
    indicators: list[str] | None = None,
):
    if tool_name == "fetch_ohlcv":
        return fetch_ohlcv(symbol, lookback_days, timeframe)
    if tool_name == "calculate_rsi":
        return calculate_rsi(symbol, 14, lookback_days, timeframe)
    if tool_name == "calculate_macd":
        return calculate_macd(symbol, 12, 26, 9, lookback_days, timeframe)
    if tool_name == "compute_indicators_multi":
        return compute_indicators_multi(symbols or [symbol], indicators)
    return {"error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Technical indicator MCP server (simple fallback mode)")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--tool", choices=["fetch_ohlcv", "calculate_rsi", "calculate_macd", "compute_indicators_multi"], default="fetch_ohlcv")
    parser.add_argument("--symbol", default="TSLA")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--indicators", default="rsi,macd,sma_50,ema_20,bollinger")
    parser.add_argument("--lookback-days", type=int, default=180)
    parser.add_argument("--timeframe", default="1Day")
    args = parser.parse_args()

    if args.probe:
        print(json.dumps(_probe(
            args.tool,
            args.symbol,
            args.lookback_days,
            args.timeframe,
            symbols=[item.strip().upper() for item in args.symbols.split(",") if item.strip()],
            indicators=[item.strip().lower() for item in args.indicators.split(",") if item.strip()],
        ), indent=2))
        raise SystemExit(0)

    mcp.run(transport="stdio")
