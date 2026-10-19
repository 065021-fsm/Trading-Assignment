import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SERVER_PATH = ROOT / "servers" / "technical_indicators_mcp_server.py"
ALPACA_SERVER_PATH = ROOT.parent / "alpaca" / "servers" / "alpaca_trading_mcpServer.py"
PROJECT_ROOT = REPO_ROOT
PORTFOLIO_CONFIG_PATH = PROJECT_ROOT / "config" / "portfolios.yaml"
RISK_CONFIG_PATH = PROJECT_ROOT / "config" / "risk.yaml"


def summarize_signal(
    rsi_value: float,
    macd_value: float,
    cash: float = 300000.0,
    indicators: list[str] | None = None,
    indicator_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected = list(dict.fromkeys(indicators or ["rsi", "macd"]))
    values = indicator_values or {}
    votes = {}
    if "rsi" in selected:
        votes["rsi"] = "BUY" if rsi_value < 40 else "SELL" if rsi_value > 60 else "HOLD"
    if "macd" in selected:
        macd_data = values.get("macd", {})
        histogram = macd_data.get("histogram") if isinstance(macd_data, dict) else None
        macd_signal = macd_data.get("signal") if isinstance(macd_data, dict) else None
        if histogram is not None:
            votes["macd"] = "BUY" if histogram > 0 else "SELL" if histogram < 0 else "HOLD"
        elif macd_signal is not None and isinstance(macd_data, dict):
            votes["macd"] = "BUY" if macd_value > macd_signal else "SELL" if macd_value < macd_signal else "HOLD"
        else:
            votes["macd"] = "BUY" if macd_value > 0 else "SELL" if macd_value < 0 else "HOLD"
    for name in ("sma_50", "ema_20", "bollinger"):
        if name in selected:
            votes[name] = str(values.get(name, {}).get("signal", "HOLD")).upper()

    buys = sum(vote == "BUY" for vote in votes.values())
    sells = sum(vote == "SELL" for vote in votes.values())
    total = len(votes)
    if total and buys > total / 2:
        if cash <= 0:
            return {"action": "HOLD", "reason": f"{buys} of {total} indicators are bullish, but this student has no reserved cash."}
        return {"action": "BUY", "reason": f"{buys} of {total} selected indicators are bullish."}
    if total and sells > total / 2:
        return {"action": "SELL", "reason": f"{sells} of {total} selected indicators are bearish."}
    return {"action": "HOLD", "reason": f"No majority: {buys} bullish, {sells} bearish, {total - buys - sells} neutral of {total} indicators."}


def build_execution_plan(action: str, symbol: str, qty: float = 1.0, dry_run: bool = True) -> dict[str, Any]:
    normalized = str(action).upper()
    if normalized == "BUY":
        return {"symbol": symbol.upper(), "action": "BUY", "side": "buy", "qty": float(qty), "dry_run": bool(dry_run), "status": "planned"}
    if normalized == "SELL":
        return {"symbol": symbol.upper(), "action": "SELL", "side": "sell", "qty": float(qty), "dry_run": bool(dry_run), "status": "planned"}
    return {"symbol": symbol.upper(), "action": "HOLD", "side": "hold", "qty": float(qty), "dry_run": bool(dry_run), "status": "skipped"}


def _read_yaml(path: Path):
    if yaml is None:
        raise RuntimeError("PyYAML is required for config parsing")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def build_portfolio_watchlist(portfolio_name: str = "bhavya_goel", symbol_focus: str | None = None) -> dict[str, Any]:
    portfolios_cfg = _read_yaml(PORTFOLIO_CONFIG_PATH)
    risk_cfg = _read_yaml(RISK_CONFIG_PATH)

    portfolio = portfolios_cfg.get("portfolios", {}).get(portfolio_name)
    if portfolio is None:
        raise KeyError(f"Unknown portfolio: {portfolio_name}")

    max_positions = int(risk_cfg.get("max_portfolio_positions", 15))
    max_single_position = float(risk_cfg.get("max_single_position_pct", 0.25))
    starting_capital = float(portfolio.get("capital", portfolios_cfg.get("capital_per_student", 300000.0)))
    cash_reserve_pct = float(portfolio.get("cash_reserve", 0.0) or 0.0)

    items = []
    for holding in portfolio.get("holdings", []):
        symbol = str(holding.get("symbol", "")).upper()
        if symbol_focus and symbol != symbol_focus.upper():
            continue
        weight = float(holding.get("weight", 0.0) or 0.0)
        items.append({
            "symbol": symbol,
            "weight": weight,
            "sector": holding.get("sector", "unknown"),
            "type": holding.get("type", "core"),
            "within_max_position": weight <= max_single_position,
        })

    items = sorted(items, key=lambda item: item["weight"], reverse=True)
    if max_positions and len(items) > max_positions:
        items = items[:max_positions]

    return {
        "portfolio": portfolio_name,
        "display": portfolio.get("display", portfolio_name),
        "max_positions": max_positions,
        "max_single_position_pct": max_single_position,
        "starting_capital": starting_capital,
        "cash_reserve_pct": cash_reserve_pct,
        "cash_reserve": starting_capital * cash_reserve_pct,
        "watchlist": items,
        "is_constrained": len(items) <= max_positions,
    }


def build_common_portfolio_view() -> dict[str, Any]:
    portfolios_cfg = _read_yaml(PORTFOLIO_CONFIG_PATH)
    risk_cfg = _read_yaml(RISK_CONFIG_PATH)
    portfolios = portfolios_cfg.get("portfolios", {})

    symbol_counts: dict[str, int] = {}
    symbol_weights: dict[str, float] = {}
    for name in portfolios:
        for holding in portfolios[name].get("holdings", []):
            symbol = str(holding.get("symbol", "")).upper()
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
            symbol_weights[symbol] = symbol_weights.get(symbol, 0.0) + float(holding.get("weight", 0.0) or 0.0)

    combined = [
        {
            "symbol": symbol,
            "weight": round(symbol_weights[symbol], 4),
            "count": symbol_counts[symbol],
            "within_max_position": symbol_weights[symbol] <= float(risk_cfg.get("max_single_position_pct", 0.25)),
        }
        for symbol in [s for s, _ in sorted(symbol_weights.items(), key=lambda kv: kv[1], reverse=True)]
    ]
    max_positions = int(risk_cfg.get("max_portfolio_positions", 15))
    combined = combined[:max_positions]

    return {
        "portfolio": "common",
        "display": portfolios_cfg.get("common", {}).get("display", "Group 8 Common Portfolio"),
        "student_count": len(portfolios),
        "combined_symbols": combined,
        "max_positions": max_positions,
        "is_constrained": len(combined) <= max_positions,
    }


def build_trading_summary(
    portfolio_name: str = "bhavya_goel",
    symbol: str = "TSLA",
    dry_run: bool = True,
    indicators: list[str] | None = None,
    cash_balance: float | None = None,
    include_llm: bool = True,
    indicator_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portfolio_view = build_portfolio_watchlist(portfolio_name, symbol_focus=symbol)
    common_view = build_common_portfolio_view()
    analysis = analyze_symbol(
        symbol,
        dry_run=dry_run,
        indicators=indicators,
        cash_balance=cash_balance,
        include_llm=include_llm,
        indicator_values=indicator_values,
    )

    return {
        "portfolio": portfolio_name,
        "symbol": symbol.upper(),
        "status": "ok",
        "signal": analysis["signal"]["action"],
        "signal_reason": analysis["signal"]["reason"],
        "indicators": analysis["indicators"],
        "portfolio_watchlist": portfolio_view,
        "common_portfolio": common_view,
        "trade_execution": analysis["trade_execution"],
        "llm_summary": analysis["llm_summary"],
    }


def direct_demo(symbol: str):
    import pandas as pd

    def rsi(series, period=14):
        delta = series.diff()
        gains = delta.clip(lower=0)
        losses = (-delta.clip(upper=0))
        avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        avg_gain_last = float(avg_gain.iloc[-1])
        avg_loss_last = float(avg_loss.iloc[-1])

        if abs(avg_loss_last) < 1e-12:
            return 100.0 if avg_gain_last > 0 else 50.0

        rs = avg_gain_last / avg_loss_last
        return 100 - (100 / (1 + rs))

    base = 250.0 if symbol == "TSLA" else 100.0
    indices = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("D"), periods=30, freq="D")
    closes = pd.Series([base * (1.005 + (idx / 100.0)) for idx in range(len(indices))])
    last = float(rsi(closes))
    return {
        "symbol": symbol,
        "status": "demo-ok",
        "rsi": round(last, 2),
        "signal": "Oversold" if last < 30 else "Overbought" if last > 70 else "Neutral",
    }


def probe_server(symbol: str):
    cmd = [
        sys.executable,
        str(SERVER_PATH),
        "--probe",
        "--tool",
        "fetch_ohlcv",
        "--symbol",
        symbol,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy(), check=False)
    print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode


def probe_indicator(symbol: str, tool: str):
    cmd = [
        sys.executable,
        str(SERVER_PATH),
        "--probe",
        "--tool",
        tool,
        "--symbol",
        symbol,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy(), check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Indicator server probe failed for {tool}: {result.stderr.strip() or result.stdout.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": result.stdout.strip(), "tool": tool}


def probe_indicators(symbols: list[str], indicators: list[str]) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(SERVER_PATH),
        "--probe",
        "--tool",
        "compute_indicators_multi",
        "--symbols",
        ",".join(symbols),
        "--indicators",
        ",".join(indicators),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy(), check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Indicator batch probe failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Indicator batch probe returned invalid JSON: {result.stdout.strip()}") from exc


def probe_account():
    cmd = [
        sys.executable,
        str(ALPACA_SERVER_PATH),
        "--probe",
        "--tool",
        "get_account",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy(), check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Account server probe failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": result.stdout.strip()}


def execute_trade(
    symbol: str,
    action: str,
    qty: float = 1.0,
    dry_run: bool = True,
    portfolio_name: str = "shared",
) -> dict[str, Any]:
    plan = build_execution_plan(action, symbol, qty=qty, dry_run=dry_run)
    if plan["action"] == "HOLD":
        return {**plan, "status": "skipped", "message": "No order was placed."}
    if dry_run:
        return {**plan, "status": "dry-run", "message": "Order planned only; no order was sent."}

    tool = "buy_stock" if plan["side"] == "buy" else "sell_stock"
    cmd = [
        sys.executable,
        str(ALPACA_SERVER_PATH),
        "--probe",
        "--tool",
        tool,
        "--symbol",
        symbol,
        "--qty",
        str(qty),
        "--portfolio",
        portfolio_name,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy(), check=False)
    payload = json.loads(result.stdout) if result.stdout.strip() else {"error": result.stderr.strip()}
    order_ok = bool(payload.get("ok"))
    return {
        **plan,
        "server_result": payload,
        "status": "submitted" if result.returncode == 0 and order_ok else "failed",
        "dry_run": bool(dry_run),
    }


def analyze_symbol(
    symbol: str,
    dry_run: bool = True,
    indicators: list[str] | None = None,
    cash_balance: float | None = None,
    include_llm: bool = True,
    indicator_values: dict[str, Any] | None = None,
):
    selected = indicators or ["rsi", "macd", "sma_50", "ema_20", "bollinger"]
    available = {"rsi", "macd", "sma_50", "ema_20", "bollinger"}
    if not selected or any(name not in available for name in selected):
        raise ValueError("Choose one or more supported technical indicators.")
    if indicator_values is None:
        indicator_values = probe_indicators([symbol], selected).get(symbol.upper(), {})
    rsi_data = {"rsi": indicator_values.get("rsi")}
    macd_result = indicator_values.get("macd", {})
    macd_data = {"macd": macd_result.get("macd")} if isinstance(macd_result, dict) else {"macd": macd_result}
    account_data = probe_account() if cash_balance is None else {"cash": float(cash_balance), "source": "student-portfolio"}

    rsi_value = float(rsi_data.get("rsi", 50.0) or 50.0)
    macd_value = float(macd_data.get("macd", 0.0) or 0.0)
    cash_value = float(account_data.get("cash", 300000.0) or 0.0)

    signal = summarize_signal(
        rsi_value,
        macd_value,
        cash_value,
        indicators=selected,
        indicator_values=indicator_values,
    )

    if include_llm:
        try:
            from core.llm import call_llm_with_fallback, get_llm_config
            cfg = get_llm_config()
            prompt = (
                f"You are a cautious trading analyst. Symbol={symbol}. "
                f"Indicators={', '.join(selected)}. RSI={rsi_value:.2f}, MACD={macd_value:.4f}. "
                f"Cash={cash_value:.0f}. "
                f"Recommend one action: BUY, SELL, or HOLD. Keep it to one short sentence."
            )
            llm_result = call_llm_with_fallback(prompt, preferred_provider=cfg.get("provider") or "ollama_local")
            explanation = llm_result.get("response", "No LLM response.")
        except Exception as exc:  # pragma: no cover
            explanation = f"LLM unavailable: {exc}"
    else:
        explanation = "LLM commentary disabled; the deterministic indicator signal is authoritative."

    execution_plan = build_execution_plan(signal["action"], symbol, qty=1.0, dry_run=dry_run)
    execution_result = execute_trade(symbol, signal["action"], qty=1.0, dry_run=dry_run) if signal["action"] in {"BUY", "SELL"} else {**execution_plan, "status": "skipped"}

    return {
        "symbol": symbol,
        "status": "analysis-ok",
        "account": account_data,
        "indicators": {name: indicator_values.get(name) for name in selected},
        "signal": signal,
        "llm_summary": explanation,
        "execution_plan": execution_plan,
        "trade_execution": execution_result,
    }


def main():
    parser = argparse.ArgumentParser(description="Minimal CrewAI/MCP technical-analysis demo")
    parser.add_argument("--mode", choices=["single", "multi"], default="single")
    parser.add_argument("--symbol", default="TSLA")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    print(f"Running in {args.mode} mode for {symbol} (dry_run={args.dry_run})")

    # Prefer to exercise the server contract directly, even when CrewAI isn't installed.
    probe_server(symbol)
    print(json.dumps(build_trading_summary(portfolio_name="bhavya_goel", symbol=symbol, dry_run=args.dry_run), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
