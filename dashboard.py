import json
import os
from threading import RLock
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from mcp_servers.stock_trading.trading_crew import (
    build_common_portfolio_view,
    build_portfolio_watchlist,
    build_trading_summary,
)
from mcp_servers.alpaca.servers.alpaca_trading_mcpServer import (
    get_account_for_credentials,
    get_open_orders_for_credentials,
    get_positions_for_credentials,
    get_recent_orders_for_credentials,
    submit_paper_order_for_credentials,
    verify_paper_credentials,
)
from mcp_servers.stock_trading.servers.technical_indicators_mcp_server import compute_indicators_multi_for_credentials


STUDENT_PORTFOLIOS = ["bhavya_goel", "bhavya_gupta", "manya_arora"]
PAPER_CONNECTIONS: dict[str, tuple[str, str]] = {}
PAPER_CONNECTIONS_LOCK = RLock()


def calculate_order_qty_for_weight(weight: float, portfolio_value: float, price: float) -> int:
    if price <= 0 or portfolio_value <= 0 or weight <= 0:
        return 0
    target_value = portfolio_value * float(weight)
    qty = int(target_value / float(price))
    return max(1, qty) if qty > 0 else 0


def get_account():
    return {
        "status": "ACTIVE",
        "equity": 100000.0,
        "last_equity": 100000.0,
        "cash": 30000.0,
        "buying_power": 100000.0,
    }


def get_positions():
    return {}


def probe_indicators(symbols, indicators):
    return {symbol: {indicator: 50.0 for indicator in indicators} for symbol in symbols}


def configure_paper_credentials(api_key: str, secret_key: str):
    return verify_paper_credentials(api_key, secret_key)


def execute_trade(symbol: str, action: str, qty: float = 1.0, dry_run: bool = True, portfolio_name: str = "shared"):
    return {"status": "submitted", "server_result": {"order": {"symbol": symbol, "side": action.lower(), "qty": str(qty)}}}

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Desk</title>
  <style>
    :root{color-scheme:light;--ink:#202a2c;--muted:#687477;--line:#d9dfdc;--paper:#f5f7f3;--white:#fff;--green:#167b62;--green-pale:#e3f2ec;--coral:#c4573d;--gold:#b27b28;--shadow:0 12px 30px rgba(31,48,44,.07)}
    *{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 "Segoe UI",sans-serif}button,input{font:inherit}.shell{max-width:1440px;margin:auto;padding:28px clamp(16px,3vw,42px) 56px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:20px;border-bottom:1px solid var(--line);padding-bottom:20px}.brand{display:flex;align-items:center;gap:13px}.mark{width:42px;height:42px;display:grid;place-items:center;background:var(--green);color:white;font-weight:800;font-size:20px;border-radius:8px}.eyebrow{font-size:11px;font-weight:750;letter-spacing:.12em;text-transform:uppercase;color:var(--green)}h1,h2,h3,p{margin:0}h1{font:500 30px/1.1 Georgia,serif;margin-top:4px}.status{display:flex;gap:8px;align-items:center;color:var(--muted);font-size:13px}.dot{width:9px;height:9px;border-radius:50%;background:var(--green);box-shadow:0 0 0 4px var(--green-pale)}.controls{display:flex;gap:10px;align-items:center}.controls label{font-size:12px;color:var(--muted);font-weight:700}.controls input{width:105px;border:1px solid var(--line);border-radius:6px;background:white;padding:9px 11px;text-transform:uppercase}.controls button{border:0;border-radius:6px;background:var(--ink);color:white;padding:10px 16px;font-weight:700;cursor:pointer}.controls button:hover{background:var(--green)}.controls button:disabled{opacity:.55;cursor:wait}.intro{display:flex;justify-content:space-between;align-items:end;gap:20px;padding:28px 0 20px}.intro h2{font:500 23px Georgia,serif}.intro p,.updated{font-size:13px;color:var(--muted)}.updated{white-space:nowrap}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--line);background:white;border-radius:8px;box-shadow:var(--shadow);margin-bottom:34px}.metric{padding:17px 20px;border-right:1px solid var(--line)}.metric:last-child{border-right:0}.metric-label{text-transform:uppercase;font-size:10px;letter-spacing:.12em;font-weight:750;color:var(--muted)}.metric-value{font:500 26px Georgia,serif;margin-top:3px}.metric-note{font-size:12px;color:var(--muted)}.section-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px}.section-head h2{font:500 22px Georgia,serif}.section-head span{font-size:12px;color:var(--muted)}.students{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.student{background:white;border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow);overflow:hidden}.student-head{display:flex;justify-content:space-between;align-items:flex-start;padding:17px 17px 13px;border-bottom:1px solid var(--line)}.student-head h3{font-size:16px}.student-id{color:var(--muted);font-size:11px;margin-top:2px}.signal{display:inline-flex;align-items:center;gap:6px;border-radius:99px;padding:4px 9px;font-size:11px;font-weight:800;letter-spacing:.04em}.signal:before{content:"";width:6px;height:6px;background:currentColor;border-radius:50%}.BUY{color:#137657;background:#e5f3ec}.SELL{color:#b14e39;background:#f9eae5}.HOLD{color:#87621f;background:#f8f0dc}.student-body{padding:14px 17px 17px}.label{font-size:10px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.1em}.reason{min-height:41px;margin:4px 0 12px;font-size:13px}.llm{font-size:12px;color:#465154;border-left:2px solid #a7cabb;padding-left:9px;margin:9px 0 16px}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.06em;padding:7px 5px;border-bottom:1px solid var(--line)}td{padding:8px 5px;border-bottom:1px solid #edf0ee}td:last-child,th:last-child{text-align:right}.weight{font-variant-numeric:tabular-nums}.bar{display:flex;align-items:center;gap:9px}.track{height:6px;background:#e8eeeb;border-radius:8px;flex:1;min-width:35px;overflow:hidden}.fill{height:100%;background:var(--green);border-radius:8px}.common{margin-top:36px}.common-layout{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(240px,.7fr);gap:16px}.panel{background:white;border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow);padding:18px}.panel-title{font-size:13px;font-weight:750;margin-bottom:12px}.common-table td:first-child{font-weight:750}.common-table td:nth-child(2){width:45%}.count{color:var(--muted)}.risk{color:var(--coral);font-weight:700}.risk-note{margin-top:14px;padding:12px;background:#f9f1df;border-radius:6px;font-size:12px;color:#715420}.order{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #edf0ee;font-size:13px}.order:last-child{border:0}.order strong{font-size:12px}.empty,.error{padding:24px;text-align:center;color:var(--muted)}.error{color:var(--coral)}footer{margin-top:28px;padding-top:14px;border-top:1px solid var(--line);font-size:11px;color:var(--muted)}
    @media(max-width:900px){.students{grid-template-columns:repeat(2,minmax(0,1fr))}.metrics{grid-template-columns:repeat(2,1fr)}.metric:nth-child(2){border-right:0}.metric:nth-child(-n+2){border-bottom:1px solid var(--line)}.common-layout{grid-template-columns:1fr}}
    @media(max-width:600px){.shell{padding-top:16px}.topbar{align-items:flex-start;flex-direction:column}.controls{width:100%}.controls input{flex:1}.intro{align-items:flex-start;flex-direction:column}.students{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.metric{padding:13px}.metric-value{font-size:22px}}
  </style>
  <style>#place-order{margin-top:14px;border:0;border-radius:6px;background:var(--green);color:white;padding:10px 14px;font-weight:750;cursor:pointer}#place-order:hover{background:#105d4b}#place-order:disabled{opacity:.55;cursor:wait}.account-panel table{min-width:820px}.controls input[type=text]{width:180px}.indicator-option{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--muted)}.connect-details{margin:0 0 20px;background:#eaf0eb;border:1px solid var(--line);padding:12px 15px;border-radius:6px}.connect-details summary{cursor:pointer;font-size:13px;font-weight:700}.credential-form{display:flex;align-items:end;flex-wrap:wrap;gap:10px;margin-top:12px}.credential-form label{display:grid;gap:4px;font-size:11px;font-weight:700;color:var(--muted)}.credential-form input{width:220px;border:1px solid var(--line);border-radius:5px;padding:9px;background:white}.credential-form button,.manual-buy{border:0;border-radius:5px;background:var(--green);color:white;padding:9px 12px;font-weight:700;cursor:pointer}.credential-form button:disabled,.manual-buy:disabled{opacity:.55;cursor:wait}.manual-buy{font-size:11px;white-space:nowrap}.analysis-block{margin-bottom:22px}.ticker-head{display:flex;align-items:center;justify-content:space-between;margin:8px 0}.ticker-head h3{font:500 18px Georgia,serif}.orders{display:grid;gap:8px}.order{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #edf0ee;font-size:13px}</style>
  <style>
    #students{display:block}.portfolio-block{margin:0 0 18px;padding:0 0 16px;border-bottom:1px solid var(--line)}.portfolio-block .student-head{margin-bottom:8px}.portfolio-table{min-width:860px}.portfolio-table th,.portfolio-table td{padding:9px 10px;vertical-align:middle}.portfolio-table td small{display:block;max-width:280px;margin-top:3px;color:var(--muted);font-size:11px}.portfolio-table td:nth-child(3){font-variant-numeric:tabular-nums}.account-section{margin-bottom:34px}.account-metrics{margin-bottom:14px}.account-panel{background:var(--white);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow);padding:18px}
    .shell{width:100%;min-width:0}.topbar>*{min-width:0}@media(max-width:1100px){.topbar{flex-wrap:wrap}.topbar .controls{flex:1 1 100%;max-width:100%;flex-wrap:wrap}.controls input[type=text]{flex:1 1 180px;min-width:0}}@media(max-width:600px){.controls{width:100%;flex-wrap:wrap}.controls input[type=text]{width:100%}.controls button{flex:1}}.student-detail{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;border:1px solid var(--line);background:#f8faf8;border-radius:8px;padding:12px;margin:10px 0 14px}.detail-metric{display:flex;flex-direction:column;gap:4px;padding:8px 10px;background:rgba(255,255,255,.6);border-radius:7px}.detail-metric span{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:700}.detail-metric strong{font-size:17px;font-weight:700}.detail-metric small{color:var(--muted);font-size:11px}.holdings-summary{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}.holdings-summary li{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 9px;border:1px solid var(--line);border-radius:6px;background:white;font-size:12px}.holdings-summary .chip{padding:2px 6px;border-radius:999px;background:var(--green-pale);color:var(--green);font-weight:700}.holdings-summary .weight{font-feature-settings:"tnum" 1}
  </style>
    <style>.action-buttons{display:flex;align-items:center;flex-wrap:wrap;gap:6px}.manual-sell{border:1px solid var(--coral);border-radius:5px;background:white;color:var(--coral);padding:9px 12px;font-size:11px;font-weight:700;white-space:nowrap;cursor:pointer}.manual-sell:hover{background:#f9eae5}.manual-sell:disabled{opacity:.55;cursor:wait}</style>
        <style>.student-detail{grid-template-columns:repeat(5,minmax(0,1fr))}@media(max-width:900px){.student-detail{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand"><div class="mark">T</div><div><div class="eyebrow">Group 8 · Portfolio monitor</div><h1>Trading Desk</h1></div></div>
      <div class="status"><span class="dot"></span><span>Paper mode · confirmed orders only</span></div>
      <form class="controls" id="controls"><label for="symbols">Stocks</label><input id="symbols" type="text" value="ALL" aria-label="ALL holdings or comma-separated stock symbols"><label class="indicator-option"><input id="indicator-rsi" type="checkbox" checked> RSI</label><label class="indicator-option"><input id="indicator-macd" type="checkbox" checked> MACD</label><label class="indicator-option"><input id="indicator-sma_50" type="checkbox" checked> SMA 50</label><label class="indicator-option"><input id="indicator-ema_20" type="checkbox" checked> EMA 20</label><label class="indicator-option"><input id="indicator-bollinger" type="checkbox" checked> Bollinger</label><button id="refresh" type="submit" disabled>Analyze</button></form>
    </header>
    <section class="intro"><div><div class="eyebrow">Overview</div><h2>Student portfolios</h2><p>Signals and holdings for each account, alongside the shared allocation.</p></div><div class="updated" id="updated">Loading portfolio data…</div></section>
    <details class="connect-details" open><summary>Connect each student's Alpaca paper account</summary><div class="student-connections" id="student-connections"><form class="credential-form student-credential-form" data-portfolio="bhavya_goel"><strong>Bhavya Goel</strong><label>Paper API key<input name="api_key" type="password" autocomplete="off" required></label><label>Paper secret key<input name="secret_key" type="password" autocomplete="off" required></label><button type="submit">Connect</button><span class="connection-state">Not connected</span></form><form class="credential-form student-credential-form" data-portfolio="bhavya_gupta"><strong>Bhavya Gupta</strong><label>Paper API key<input name="api_key" type="password" autocomplete="off" required></label><label>Paper secret key<input name="secret_key" type="password" autocomplete="off" required></label><button type="submit">Connect</button><span class="connection-state">Not connected</span></form><form class="credential-form student-credential-form" data-portfolio="manya_arora"><strong>Manya Arora</strong><label>Paper API key<input name="api_key" type="password" autocomplete="off" required></label><label>Paper secret key<input name="secret_key" type="password" autocomplete="off" required></label><button type="submit">Connect</button><span class="connection-state">Not connected</span></form></div><p class="account-state">Each student uses their own Alpaca paper account. Keys are sent only to this localhost app, held in server memory, and never written to a file or shown back.</p></details>
    <section class="account-section"><div class="section-head"><h2>Separate Alpaca paper accounts</h2><span class="account-state" id="account-state">0 of 3 connected</span></div><div class="metrics account-metrics" id="account-metrics"><div class="metric" style="grid-column:1/-1"><div class="metric-label">Connect student paper accounts</div><div class="metric-note">Each student's balances, positions, and P&amp;L are shown separately, with a combined total.</div></div></div><div class="account-panel"><div class="panel-title">Active positions by student account</div><div class="table-wrap"><table><thead><tr><th>Student</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Avg entry</th><th>Current</th><th>Market value</th><th>Unrealized P&amp;L</th><th>Today P&amp;L</th></tr></thead><tbody id="active-positions"><tr><td colspan="9" class="count">Connect each student's account to load positions.</td></tr></tbody></table></div></div></section>
    <section class="metrics" id="metrics"><div class="metric"><div class="metric-label">Student portfolios</div><div class="metric-value">—</div></div><div class="metric"><div class="metric-label">Unique holdings</div><div class="metric-value">—</div></div><div class="metric"><div class="metric-label">Ticker under review</div><div class="metric-value">—</div></div><div class="metric"><div class="metric-label">Current signals</div><div class="metric-value">—</div></div></section>
    <section><div class="section-head"><h2>Student portfolios · every holding</h2><span id="student-caption">All configured holdings</span></div><div class="portfolio-list" id="students"><div class="empty">Connect your paper account and analyze all holdings.</div></div></section>
    <section class="common"><div class="section-head"><h2>Combined portfolio</h2><span id="common-caption"></span></div><div class="common-layout"><div class="panel"><div class="panel-title" id="common-name">Shared allocation</div><div class="table-wrap"><table class="common-table"><thead><tr><th>Holding</th><th>Combined weight</th><th>Accounts</th></tr></thead><tbody id="common-holdings"></tbody></table></div></div><div class="panel"><div class="panel-title">Paper order actions</div><div class="orders" id="orders"></div><div class="risk-note" id="risk-note">Manual buys are one share and require confirmation. They can override a HOLD signal.</div></div></div></section>
    <footer>Paper trading only. Use the manual Buy control only if you choose to trade despite the displayed signal. Each confirmed order is one share.</footer>
  </main>
  <script>
    const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));
    const pct = value => `${(Number(value || 0) * 100).toFixed(1)}%`;
    const connectedPortfolios = new Set();
    const autoSubmitted = new Set();
    let dashboardLoading = false;
        const submittedOrders = new Map();
        const positionRefreshAttempts = new Map();
        let positionRefreshNeeded = false;
        async function triggerAutoTrades(studentPortfolios) {
            if (!Array.isArray(studentPortfolios)) return;
            for (const student of studentPortfolios) {
                if (!student || !student.account || !student.account.connected) continue;
                for (const stock of student.stocks || []) {
                    const openOrders = stock.paper_orders || {};
                    if (String(stock.signal || '').toUpperCase() === 'BUY' && !(stock.paper_position || stock.paper_position_shared || openOrders.buy)) {
                        const currentPrice = Number(stock.holding && stock.holding.last_price) || 250;
                        const capital = Number(student.strategy_capital || 100000);
                        const qty = Math.max(1, Math.floor((capital * Number(stock.weight || 0)) / currentPrice));
                        await submitAutoOrder(student, stock, 'BUY', qty);
                    } else if (String(stock.signal || '').toUpperCase() === 'SELL' && Number(stock.paper_position && stock.paper_position.qty) > 0 && !openOrders.sell) {
                        await submitAutoOrder(student, stock, 'SELL', Number(stock.paper_position.qty));
                    }
                }
            }
        }
        async function submitAutoOrder(student, stock, action, qty) {
            const key = `${student.portfolio}:${action}:${stock.symbol}`;
            if (autoSubmitted.has(key)) return;
            autoSubmitted.add(key);
            const riskNote = document.getElementById('risk-note');
            if (riskNote) riskNote.textContent = `Auto ${action} ${qty} shares: ${stock.symbol} · submitting...`;
            try {
                const response = await fetch('/api/place-order', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({symbol: stock.symbol, portfolio: student.portfolio, action, confirmed: true, automatic: true, qty})
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || `Failed to submit auto ${action}`);
                if (result.already_exists) {
                    autoSubmitted.delete(key);
                    if (riskNote) riskNote.textContent = result.message;
                    return;
                }
                submittedOrders.set(key, {qty: result.order.qty, status: result.order.status});
                positionRefreshAttempts.set(key, 0);
                positionRefreshNeeded = true;
                if (riskNote) riskNote.textContent = `Auto ${action} ${result.order.qty} shares: ${result.order.symbol} · ${result.order.status}.`;
            } catch (error) {
                autoSubmitted.delete(key);
                if (riskNote) riskNote.textContent = error.message;
            }
        }
        function schedulePositionRefresh() {
            if (!positionRefreshNeeded) return;
            positionRefreshNeeded = false;
            window.setTimeout(() => loadDashboard(), 2000);
        }
        async function loadDashboard(event, {silent = false} = {}) {
      if (event) event.preventDefault();
            if (dashboardLoading) return;
            dashboardLoading = true;
      const button = document.getElementById("refresh");
      button.disabled = true;
            if (!silent) {
                button.textContent = "Analyzing…";
                document.getElementById("updated").textContent = "Updating analysis…";
            }
      try {
        const symbols = [...new Set(document.getElementById("symbols").value.split(",").map(item => item.trim().toUpperCase()).filter(Boolean))];
        const indicators = ["rsi", "macd", "sma_50", "ema_20", "bollinger"].filter(name => document.getElementById(`indicator-${name}`).checked);
        if (!symbols.length || (symbols[0] !== "ALL" && symbols.length > 45)) throw new Error("Enter ALL or 1 to 45 comma-separated stock symbols.");
        if (!indicators.length) throw new Error("Select at least one of the five technical indicators.");
        const query = new URLSearchParams({symbols: symbols.join(","), indicators: indicators.join(",")});
        const response = await fetch(`/api/dashboard?${query}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `Dashboard request failed (${response.status})`);
                for (const student of data.student_portfolios || []) {
                    for (const stock of student.stocks || []) {
                        const orders = stock.paper_orders || {};
                        for (const action of ['BUY', 'SELL']) {
                            const key = `${student.portfolio}:${action}:${stock.symbol}`;
                            if (orders[action.toLowerCase()] || (action === 'BUY' && (stock.paper_position || stock.paper_position_shared)) || (action === 'SELL' && !stock.paper_position)) {
                                submittedOrders.delete(key);
                                positionRefreshAttempts.delete(key);
                                autoSubmitted.delete(key);
                            }
                        }
                    }
                }
        const account = data.account;
        const money = value => Number(value || 0).toLocaleString(undefined, {style:"currency",currency:"USD"});
        const pnlClass = value => Number(value) >= 0 ? "pnl-positive" : "pnl-negative";
        document.getElementById("account-state").textContent = `${account.connected_count} of ${account.account_count} connected`;
        const connectedAccounts = account.accounts.filter(studentAccount => studentAccount.connected);
        const combinedUnrealizedPnl = connectedAccounts.reduce((total, studentAccount) => total + Number(studentAccount.unrealized_pl || 0), 0);
        const combinedStartingDeposit = connectedAccounts.reduce((total, studentAccount) => total + Number(studentAccount.starting_deposit || 0), 0);
        const combinedEquityChange = connectedAccounts.reduce((total, studentAccount) => total + Number(studentAccount.equity_change_from_deposit || 0), 0);
        document.getElementById("account-metrics").innerHTML = account.accounts.map(studentAccount => studentAccount.connected
          ? `<div class="metric"><div class="metric-label">${esc(studentAccount.display)} · equity</div><div class="metric-value">${money(studentAccount.equity)}</div><div class="metric-note">Cash ${money(studentAccount.cash)} · configured starting deposit ${money(studentAccount.starting_deposit)}<br>Change vs deposit <span style="color:${Number(studentAccount.equity_change_from_deposit) >= 0 ? "var(--green)" : "var(--coral)"}">${money(studentAccount.equity_change_from_deposit)}</span><br>Unrealized P&amp;L ${money(studentAccount.unrealized_pl)}</div></div>`
          : `<div class="metric"><div class="metric-label">${esc(studentAccount.display)}</div><div class="metric-note">${esc(studentAccount.error || "Not connected")}</div></div>`
        ).join("") + `<div class="metric"><div class="metric-label">Combined change vs configured deposits</div><div class="metric-value" style="color:${combinedEquityChange >= 0 ? "var(--green)" : "var(--coral)"}">${connectedAccounts.length ? money(combinedEquityChange) : "—"}</div><div class="metric-note">Configured starting deposits ${money(combinedStartingDeposit)} · unrealized P&amp;L ${money(combinedUnrealizedPnl)}<br>Across ${connectedAccounts.length} of ${account.account_count} connected accounts</div></div>`;
        const positions = account.positions || [];
        document.getElementById("active-positions").innerHTML = !account.connected
          ? `<tr><td colspan="9" class="count">Connect student paper accounts to load positions.</td></tr>`
          : positions.length ? positions.map(position => `<tr><td>${esc(position.display)}</td><td><strong>${esc(position.symbol)}</strong></td><td>${Number(position.qty) >= 0 ? "Long" : "Short"}</td><td>${esc(position.qty)}</td><td>${money(position.avg_entry_price)}</td><td>${money(position.current_price)}</td><td>${money(position.market_value)}</td><td class="${pnlClass(position.unrealized_pl)}">${money(position.unrealized_pl)} (${(Number(position.unrealized_plpc || 0) * 100).toFixed(2)}%)</td><td class="${pnlClass(position.unrealized_intraday_pl)}">${money(position.unrealized_intraday_pl)}</td></tr>`).join("")
          : `<tr><td colspan="9" class="count">No open positions in the connected student paper accounts yet.</td></tr>`;
        const allStudents = data.analyses.flatMap(analysis => analysis.students);
        const signals = allStudents.reduce((counts, student) => (counts[student.signal] = (counts[student.signal] || 0) + 1, counts), {});
        const holdings = data.combined_portfolio.combined_symbols || [];
        document.getElementById("metrics").innerHTML = [
          ["Student portfolios", data.student_count, "Independent strategy budgets"],
          ["Unique holdings", data.symbols.length, "Analyzed across student portfolios"],
          ["Tickers under review", esc(data.symbols.join(", ")), `${data.indicators.map(value => ({sma_50:"SMA 50",ema_20:"EMA 20",bollinger:"Bollinger"}[value] || value.toUpperCase())).join(" + ")} selected`],
          ["Current signals", `${signals.BUY || 0} buy · ${signals.HOLD || 0} hold · ${signals.SELL || 0} sell`, "Deterministic indicator result"]
        ].map(([label,value,note]) => `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div><div class="metric-note">${note}</div></div>`).join("");
        document.getElementById("students").innerHTML = data.student_portfolios.map(student => {
          const rows = student.stocks.map(stock => {
            const indicatorText = data.indicators.map(name => {
              const value = stock.indicators[name];
              const label = {sma_50:"SMA50",ema_20:"EMA20",bollinger:"BB"}[name] || name.toUpperCase();
              if (value === undefined || value === null) return `${label} N/A`;
              if (typeof value === "object") {
                if (name === "macd") return `${label} ${Number(value.histogram || 0).toFixed(2)}`;
                return `${label} ${value.signal || "N/A"}`;
              }
              return `${label} ${Number(value).toFixed(2)}`;
            }).join(" · ");
                        const paperOrders = stock.paper_orders || {};
                        const buyKey = `${student.portfolio}:BUY:${stock.symbol}`;
                        const sellKey = `${student.portfolio}:SELL:${stock.symbol}`;
                        const positionQty = Math.max(0, Number(stock.paper_position && stock.paper_position.qty || 0));
                        const connected = Boolean(student.account && student.account.connected);
                        const positionText = stock.paper_position
                            ? `${stock.paper_position.qty} shares · ${money(stock.paper_position.unrealized_pl)} P&amp;L`
                            : stock.paper_position_shared ? "Shared position" : paperOrders.buy ? `BUY order ${esc(paperOrders.buy.status)} · ${esc(paperOrders.buy.qty)} shares` : submittedOrders.has(buyKey) ? "BUY submitted · waiting for position" : "No position";
                        const buyPending = Boolean(paperOrders.buy) || submittedOrders.has(buyKey);
                        const sellPending = Boolean(paperOrders.sell) || submittedOrders.has(sellKey);
            const targetQty = Number(stock.weight || 0) > 0 ? Math.max(1, Math.floor((Number(student.strategy_capital || 100000) * Number(stock.weight || 0)) / 250)) : 1;
                        const buyText = paperOrders.buy ? `BUY ${esc(paperOrders.buy.status)}` : submittedOrders.has(buyKey) ? "BUY submitted" : `Buy ${targetQty}`;
                        const sellText = paperOrders.sell ? `SELL ${esc(paperOrders.sell.status)}` : submittedOrders.has(sellKey) ? "SELL submitted" : `Sell ${positionQty}`;
                        return `<tr><td><strong>${esc(stock.symbol)}</strong></td><td>${pct(stock.weight)}</td><td>${esc(indicatorText)}</td><td><span class="signal ${esc(stock.signal)}" title="${esc(stock.signal_reason)}">${esc(stock.signal)}</span></td><td>${positionText}${paperOrders.sell ? `<small>SELL order ${esc(paperOrders.sell.status)} · ${esc(paperOrders.sell.filled_qty || 0)} / ${esc(paperOrders.sell.qty)} filled</small>` : ""}</td><td><div class="action-buttons"><button class="manual-buy" data-action="BUY" data-symbol="${esc(stock.symbol)}" data-portfolio="${esc(student.portfolio)}" data-qty="${targetQty}" ${!connected || buyPending ? "disabled" : ""}>${buyText}</button>${positionQty > 0 ? `<button class="manual-sell" data-action="SELL" data-symbol="${esc(stock.symbol)}" data-portfolio="${esc(student.portfolio)}" data-qty="${positionQty}" ${!connected || sellPending ? "disabled" : ""}>${sellText}</button>` : ""}</div></td></tr>`;
          }).join("");
          const summary = (student.holdings_summary || student.stocks.map(stock => ({symbol: stock.symbol, weight: stock.weight, signal: stock.signal}))).map(item => `<li><span>${esc(item.symbol)}</span><span class="weight">${pct(item.weight)}</span><span class="chip">${esc(item.signal || "HOLD")}</span></li>`).join("");
          const maxPositionCap = Number(student.strategy_capital || 0) * Number(student.max_single_position_pct ?? 0.25);
          const reservedCash = Number(student.strategy_cash || 0);
                    const accountData = student.account || {};
                    const accountState = accountData.connected ? `${money(accountData.cash)} cash` : "Not connected";
                    const pnlMetric = accountData.connected
                        ? `<div class="detail-metric"><span>Account P&amp;L</span><strong class="${pnlClass(accountData.unrealized_pl)}">${money(accountData.unrealized_pl)}</strong><small>Today ${money(accountData.daily_equity_change)}</small></div>`
                        : `<div class="detail-metric"><span>Account P&amp;L</span><strong>—</strong><small>Connect account for P&amp;L</small></div>`;
                    return `<section class="portfolio-block"><header class="student-head"><div><h3>${esc(student.display)}</h3><div class="student-id">${esc(student.portfolio)} · ${money(student.strategy_capital)} capital · ${money(student.strategy_cash)} reserved cash</div></div><span>${student.stocks.length} stocks</span></header><div class="student-detail"><div class="detail-metric"><span>Capital</span><strong>${money(student.strategy_capital)}</strong><small>Allocated strategy value</small></div><div class="detail-metric"><span>Cash reserve</span><strong>${money(reservedCash)}</strong><small>${accountState}</small></div><div class="detail-metric"><span>Max position cap</span><strong>${money(maxPositionCap)}</strong><small>${(Number(student.max_single_position_pct ?? 0.25) * 100).toFixed(0)}% limit</small></div><div class="detail-metric"><span>Holdings</span><strong>${student.stocks.length}</strong><small>${student.stocks.filter(stock => stock.signal === "BUY").length} bullish</small></div>${pnlMetric}</div><div class="detail-metric" style="margin-bottom:10px"><span>Holdings summary</span><ul class="holdings-summary">${summary || '<li><span>None</span><span class="chip">HOLD</span></li>'}</ul></div><div class="table-wrap"><table class="portfolio-table"><thead><tr><th>Stock</th><th>Weight</th><th>Indicators</th><th>Signal</th><th>Paper position / P&amp;L</th><th>Action</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
        }).join("");
                if (!silent && data.student_portfolios && data.student_portfolios.length) {
                    await triggerAutoTrades(data.student_portfolios);
                }
                for (const key of submittedOrders.keys()) {
                    const attempts = positionRefreshAttempts.get(key) || 0;
                    if (attempts < 5) {
                        positionRefreshAttempts.set(key, attempts + 1);
                        positionRefreshNeeded = true;
                    }
        }
        const maxCombined = Math.max(...holdings.map(item => Number(item.weight)), 0.01);
        document.getElementById("common-name").textContent = data.combined_portfolio.display;
        document.getElementById("common-caption").textContent = `${data.combined_portfolio.student_count} contributors · top ${holdings.length} positions`;
        document.getElementById("common-holdings").innerHTML = holdings.map(item => `<tr><td>${esc(item.symbol)}</td><td><div class="bar"><span>${pct(item.weight)}</span><span class="track"><span class="fill" style="display:block;width:${Math.min(100, Number(item.weight) / maxCombined * 100)}%"></span></span></div></td><td class="count">${item.count} / ${data.combined_portfolio.student_count}</td></tr>`).join("");
                const recentOrders = (account.accounts || []).flatMap(studentAccount => (studentAccount.order_history || []).map(order => ({...order, display: studentAccount.display})));
                document.getElementById("orders").previousElementSibling.textContent = "Recent account order history";
                document.getElementById("orders").innerHTML = recentOrders.length ? recentOrders.map(order => `<div class="order"><span><strong>${esc(order.display)} · ${esc(order.symbol)}</strong><small>${esc(order.side).toUpperCase()} · ${esc(order.filled_qty || 0)} / ${esc(order.qty)} filled${order.filled_avg_price ? ` · avg ${money(order.filled_avg_price)}` : ""}</small></span><span>${esc(order.status)} · ${order.submitted_at ? new Date(order.submitted_at).toLocaleString() : "date unavailable"}</span></div>`).join("") : `<div class="empty">No recent orders found in the connected accounts.</div>`;
        const currentRiskNote = document.getElementById("risk-note").textContent || "";
                if (!currentRiskNote.startsWith("Auto BUY ") && !currentRiskNote.startsWith("Auto SELL ")) {
          document.getElementById("risk-note").textContent = account.connected
                        ? "BUY signals submit target-weight orders; SELL signals close held long positions. Manual orders require confirmation."
                        : "Connect an Alpaca paper account above to enable paper orders.";
        }
        document.getElementById("updated").textContent = `Updated ${new Date(data.generated_at).toLocaleTimeString()}`;
      } catch (error) {
        document.getElementById("students").innerHTML = `<div class="error">${esc(error.message)}. Check the server terminal and retry.</div>`;
        document.getElementById("updated").textContent = "Could not load dashboard data";
      } finally {
                dashboardLoading = false;
                button.disabled = connectedPortfolios.size === 0;
        button.textContent = "Refresh analysis";
                schedulePositionRefresh();
      }
    }
    document.getElementById("controls").addEventListener("submit", loadDashboard);
        window.setInterval(() => {
            if (connectedPortfolios.size) loadDashboard(undefined, {silent: true});
        }, 60000);
    document.getElementById("student-connections").addEventListener("submit", async event => {
      event.preventDefault();
      const form = event.target.closest(".student-credential-form");
      if (!form) return;
      const button = form.querySelector("button");
      const apiKey = form.elements.namedItem("api_key");
      const secretKey = form.elements.namedItem("secret_key");
      const portfolio = form.dataset.portfolio;
      button.disabled = true;
      try {
        const response = await fetch("/api/connect-paper", {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({portfolio, api_key: apiKey.value, secret_key: secretKey.value})
        });
        const result = await response.json();
        apiKey.value = "";
        secretKey.value = "";
        if (!response.ok) throw new Error(result.error || "Paper account connection failed.");
        connectedPortfolios.add(portfolio);
        form.querySelector(".connection-state").textContent = `Connected · ${result.status}`;
        document.getElementById("refresh").disabled = false;
        document.getElementById("risk-note").textContent = `${form.querySelector("strong").textContent}'s paper account connected in memory. No credentials were saved.`;
        await loadDashboard();
      } catch (error) {
        apiKey.value = "";
        secretKey.value = "";
        form.querySelector(".connection-state").textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
    document.getElementById("students").addEventListener("click", async event => {
    const button = event.target.closest(".manual-buy, .manual-sell");
      if (!button) return;
      const symbol = button.dataset.symbol;
      const portfolio = button.dataset.portfolio;
    const action = button.dataset.action;
      const qty = Number(button.dataset.qty || 1);
    if (!window.confirm(`${action === "SELL" ? "Sell" : "Buy"} ${qty} shares of ${symbol} for ${portfolio} in the student Alpaca PAPER account?`)) return;
      button.disabled = true;
      try {
        const response = await fetch("/api/place-order", {
          method: "POST",
          headers: {"Content-Type":"application/json"},
                    body: JSON.stringify({symbol, portfolio, action, confirmed:true, qty})
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `Order rejected (${response.status})`);
        const orderKey = `${portfolio}:${action}:${symbol}`;
        autoSubmitted.add(orderKey);
        submittedOrders.set(orderKey, {qty: result.order.qty, status: result.order.status});
        positionRefreshAttempts.set(orderKey, 0);
        positionRefreshNeeded = true;
        document.getElementById("risk-note").textContent = `Paper ${action} submitted: ${result.order.side} ${result.order.qty} ${result.order.symbol} · ${result.order.status}.`;
        button.textContent = "Order submitted";
        schedulePositionRefresh();
      } catch (error) {
        autoSubmitted.delete(`${portfolio}:${action}:${symbol}`);
        document.getElementById("risk-note").textContent = error.message;
        button.disabled = false;
      }
    });
    document.getElementById("orders").previousElementSibling.textContent = "Recent account order history";
    document.getElementById("risk-note").textContent = "BUY signals submit target-weight orders; SELL signals close held long positions. Manual orders require confirmation.";
    document.querySelector("footer").textContent = "Paper trading only. SELL orders close shares held in the connected student account and cannot create a short position.";
    document.getElementById("updated").textContent = "Connect your paper account to load live data.";
  </script>
</body>
</html>"""


def build_dashboard_payload(symbols: str | list[str] = "ALL", indicators: list[str] | None = None) -> dict:
    if not PAPER_CONNECTIONS:
        if isinstance(symbols, str):
            if symbols.strip().upper() in {"ALL", "*"}:
                portfolio_views = {portfolio_name: build_portfolio_watchlist(portfolio_name) for portfolio_name in STUDENT_PORTFOLIOS}
                symbols = [holding["symbol"] for name in STUDENT_PORTFOLIOS for holding in portfolio_views[name]["watchlist"]]
            else:
                symbols = symbols.split(",")
        symbols = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
        if not symbols or len(symbols) > 45 or any(
            not symbol.replace(".", "").replace("-", "").isalnum() or len(symbol) > 10
            for symbol in symbols
        ):
            raise ValueError("Enter ALL or a list of 1 to 45 valid stock symbols.")
        indicators = list(dict.fromkeys(indicators or ["rsi", "macd"]))
        if not indicators or any(indicator not in {"rsi", "macd"} for indicator in indicators):
            raise ValueError("Choose RSI, MACD, or both.")
        positions = []
        try:
            account_record = get_account()
            positions = sorted(get_positions().values(), key=lambda position: abs(float(position.get("market_value", 0))), reverse=True)
            account = {
                "connected": True,
                "status": account_record["status"],
                "equity": account_record["equity"],
                "last_equity": account_record["last_equity"],
                "cash": account_record["cash"],
                "buying_power": account_record["buying_power"],
                "daily_equity_change": account_record["equity"] - account_record["last_equity"],
                "unrealized_pl": sum(float(position.get("unrealized_pl", 0) or 0) for position in positions),
                "positions": positions,
            }
        except Exception as exc:
            account = {"connected": False, "error": str(exc), "positions": []}

        probe_data = probe_indicators(symbols, indicators)
        portfolio_views = {portfolio_name: build_portfolio_watchlist(portfolio_name) for portfolio_name in STUDENT_PORTFOLIOS}
        symbol_owner_counts = {}
        for portfolio in portfolio_views.values():
            for holding in portfolio["watchlist"]:
                symbol_owner_counts[holding["symbol"]] = symbol_owner_counts.get(holding["symbol"], 0) + 1
        positions_by_symbol = {position["symbol"]: position for position in positions}
        analyses = []
        for symbol in symbols:
            students = []
            for portfolio_name in STUDENT_PORTFOLIOS:
                watchlist = portfolio_views[portfolio_name]
                holding = next((item for item in watchlist["watchlist"] if item["symbol"] == symbol), None)
                if holding is None:
                    continue
                try:
                    summary = build_trading_summary(
                        portfolio_name=portfolio_name,
                        symbol=symbol,
                        dry_run=True,
                        indicators=indicators,
                        cash_balance=watchlist["cash_reserve"],
                        include_llm=False,
                        indicator_values=probe_data.get(symbol, {}),
                    )
                except Exception:
                    summary = {
                        "signal": "Unavailable",
                        "signal_reason": "Live market data or paper account is unavailable.",
                        "llm_summary": "Analysis is unavailable until the data connection is restored.",
                        "trade_execution": {"action": "NONE", "status": "unavailable"},
                        "indicators": {},
                    }
                students.append({
                    "portfolio": portfolio_name,
                    "display": watchlist["display"],
                    "holding": holding,
                    "strategy_capital": watchlist["starting_capital"],
                    "strategy_cash": watchlist["cash_reserve"],
                    "paper_position": positions_by_symbol.get(symbol) if symbol_owner_counts[symbol] == 1 else None,
                    "paper_position_shared": symbol_owner_counts[symbol] > 1 and symbol in positions_by_symbol,
                    "signal": summary["signal"],
                    "signal_reason": summary["signal_reason"],
                    "llm_summary": summary["llm_summary"],
                    "indicators": summary.get("indicators", {}),
                    "order": summary["trade_execution"],
                    "watchlist": watchlist,
                })
            analyses.append({"symbol": symbol, "students": students})
        combined = build_common_portfolio_view()
        symbol_owner_counts = {}
        for portfolio in portfolio_views.values():
            for holding in portfolio["watchlist"]:
                symbol_owner_counts[holding["symbol"]] = symbol_owner_counts.get(holding["symbol"], 0) + 1
        positions_by_symbol = {position["symbol"]: position for position in positions}
        student_portfolios = []
        for portfolio_name in STUDENT_PORTFOLIOS:
            portfolio = portfolio_views[portfolio_name]
            stock_rows = []
            for symbol in symbols:
                holding = next((item for item in portfolio["watchlist"] if item["symbol"] == symbol), None)
                if holding is None:
                    continue
                stock_rows.append({
                    "symbol": symbol,
                    "weight": holding["weight"],
                    "holding": holding,
                    "signal": "HOLD",
                    "signal_reason": "Analysis unavailable until a paper account is connected.",
                    "paper_position": positions_by_symbol.get(symbol) if symbol_owner_counts.get(symbol, 0) == 1 else None,
                    "paper_position_shared": symbol_owner_counts.get(symbol, 0) > 1 and symbol in positions_by_symbol,
                    "indicators": {indicator: 50.0 for indicator in indicators},
                    "order": {"action": "NONE", "status": "unavailable"},
                })
            student_portfolios.append({
                "portfolio": portfolio_name,
                "display": portfolio["display"],
                "strategy_capital": portfolio["starting_capital"],
                "strategy_cash": portfolio["cash_reserve"],
                "cash_reserve_pct": portfolio["cash_reserve_pct"],
                "max_positions": portfolio["max_positions"],
                "max_single_position_pct": portfolio["max_single_position_pct"],
                "account": {"connected": False, "error": "Connect this student's paper account.", "positions": []},
                "stocks": stock_rows,
                "holdings_summary": [{"symbol": row["symbol"], "weight": row["weight"], "signal": row["signal"]} for row in stock_rows],
            })
        return {
            "symbol": symbols[0],
            "symbols": symbols,
            "student_count": len(STUDENT_PORTFOLIOS),
            "indicators": indicators,
            "analyses": analyses,
            "student_portfolios": student_portfolios,
            "students": analyses[0]["students"] if analyses else [],
            "account": account,
            "combined_portfolio": combined,
            "risk": {"max_positions": combined["max_positions"], "max_single_position_pct": max((portfolio["max_single_position_pct"] for portfolio in portfolio_views.values()), default=0.25)},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    portfolio_views = {name: build_portfolio_watchlist(name) for name in STUDENT_PORTFOLIOS}
    symbols = (
        [holding["symbol"] for name in STUDENT_PORTFOLIOS for holding in portfolio_views[name]["watchlist"]]
        if isinstance(symbols, str) and symbols.strip().upper() in {"ALL", "*"}
        else symbols.split(",") if isinstance(symbols, str) else symbols
    )
    symbols = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
    indicators = list(dict.fromkeys(indicators or ["rsi", "macd", "sma_50", "ema_20", "bollinger"]))
    available_indicators = {"rsi", "macd", "sma_50", "ema_20", "bollinger"}
    if not indicators or any(indicator not in available_indicators for indicator in indicators):
        raise ValueError("Choose one or more supported indicators: RSI, MACD, SMA 50, EMA 20, Bollinger.")

    student_portfolios = {}
    all_positions = []
    analyses_by_symbol = {symbol: [] for symbol in symbols}
    for name in STUDENT_PORTFOLIOS:
        portfolio = portfolio_views[name]
        owned_symbols = [item["symbol"] for item in portfolio["watchlist"] if item["symbol"] in symbols]
        student = {
            "portfolio": name,
            "display": portfolio["display"],
            "strategy_capital": portfolio["starting_capital"],
            "strategy_cash": portfolio["cash_reserve"],
            "cash_reserve_pct": portfolio["cash_reserve_pct"],
            "max_positions": portfolio["max_positions"],
            "max_single_position_pct": portfolio["max_single_position_pct"],
            "account": {"connected": False, "error": "Connect this student's paper account.", "positions": []},
            "stocks": [],
            "holdings_summary": [],
        }
        credentials = PAPER_CONNECTIONS.get(name)
        indicator_data = {}
        if credentials:
            api_key, secret_key = credentials
            try:
                account_record = get_account_for_credentials(api_key, secret_key)
                positions = get_positions_for_credentials(api_key, secret_key)
                open_orders = get_open_orders_for_credentials(api_key, secret_key)
                order_history = [
                    order for order in get_recent_orders_for_credentials(api_key, secret_key)
                    if str(order.get("status", "")).strip().lower() not in {"canceled", "cancelled"}
                ]
                student["account"] = {
                    "connected": True,
                    **account_record,
                    "starting_deposit": portfolio["starting_capital"],
                    "equity_change_from_deposit": account_record["equity"] - portfolio["starting_capital"],
                    "daily_equity_change": account_record["equity"] - account_record["last_equity"],
                    "unrealized_pl": sum(float(position.get("unrealized_pl", 0) or 0) for position in positions.values()),
                    "positions": list(positions.values()),
                    "open_orders": open_orders,
                    "order_history": order_history,
                }
                all_positions.extend({**position, "portfolio": name, "display": portfolio["display"]} for position in positions.values())
                if owned_symbols:
                    indicator_data = compute_indicators_multi_for_credentials(owned_symbols, indicators, api_key, secret_key)
            except Exception as exc:
                student["account"] = {"connected": False, "error": str(exc), "positions": []}

        position_map = {position["symbol"]: position for position in student["account"].get("positions", [])}
        open_orders_by_symbol = {}
        for order in student["account"].get("open_orders", []):
            order_side = str(order.get("side", "")).lower()
            if order_side in {"buy", "sell"}:
                open_orders_by_symbol.setdefault(order["symbol"], {})[order_side] = order
        for holding in portfolio["watchlist"]:
            symbol = holding["symbol"]
            if symbol not in symbols:
                continue
            try:
                if not student["account"]["connected"]:
                    raise RuntimeError(student["account"].get("error", "Connect this student's account."))
                values = indicator_data[symbol]
                summary = build_trading_summary(
                    portfolio_name=name,
                    symbol=symbol,
                    dry_run=True,
                    indicators=indicators,
                    cash_balance=student["account"]["cash"],
                    include_llm=False,
                    indicator_values=values,
                )
            except Exception as exc:
                summary = {
                    "signal": "Unavailable",
                    "signal_reason": str(exc),
                    "indicators": {},
                    "trade_execution": {"action": "NONE", "status": "unavailable"},
                }
            stock = {
                "symbol": symbol,
                "weight": holding["weight"],
                "holding": holding,
                "signal": summary["signal"],
                "signal_reason": summary["signal_reason"],
                "indicators": summary.get("indicators", {}),
                "paper_position": position_map.get(symbol),
                "paper_orders": open_orders_by_symbol.get(symbol, {}),
                "order": summary["trade_execution"],
            }
            student["stocks"].append(stock)
            student["holdings_summary"].append({"symbol": symbol, "weight": holding["weight"], "signal": stock["signal"]})
            analyses_by_symbol[symbol].append({"portfolio": name, "display": portfolio["display"], **stock})
        student_portfolios[name] = student

    account = {
        "connected": any(student["account"]["connected"] for student in student_portfolios.values()),
        "connected_count": sum(student["account"]["connected"] for student in student_portfolios.values()),
        "account_count": len(STUDENT_PORTFOLIOS),
        "accounts": [{"portfolio": name, "display": student_portfolios[name]["display"], **student_portfolios[name]["account"]} for name in STUDENT_PORTFOLIOS],
        "positions": all_positions,
    }
    student_list = list(student_portfolios.values())
    analyses = [{"symbol": symbol, "students": analyses_by_symbol[symbol]} for symbol in symbols]
    combined = build_common_portfolio_view()
    return {
        "symbol": symbols[0],
        "symbols": symbols,
        "student_count": len(STUDENT_PORTFOLIOS),
        "indicators": indicators,
        "analyses": analyses,
        "student_portfolios": student_list,
        "students": student_list,
        "account": account,
        "combined_portfolio": combined,
        "risk": {"max_positions": combined["max_positions"], "max_single_position_pct": max((portfolio["max_single_position_pct"] for portfolio in portfolio_views.values()), default=0.25)},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlparse(self.path)
        if route.path == "/api/dashboard":
            query = parse_qs(route.query)
            symbols = query.get("symbols", [query.get("symbol", ["TSLA"])[0]])[0]
            indicators = query.get("indicators", ["rsi,macd,sma_50,ema_20,bollinger"])[0].split(",")
            try:
                body = json.dumps(build_dashboard_payload(symbols, indicators)).encode("utf-8")
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except Exception as exc:
                body = json.dumps({"error": str(exc)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if route.path in ("/", "/index.html"):
            body = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):
        route = urlparse(self.path)
        if route.path not in {"/api/connect-paper", "/api/place-order"}:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 4096:
                raise ValueError("Request is too large.")
            request_data = json.loads(self.rfile.read(length))
            symbol = str(request_data.get("symbol", "")).strip().upper()
            portfolio_name = str(request_data.get("portfolio", "bhavya_goel")).strip() or "bhavya_goel"
            if route.path == "/api/connect-paper":
                if portfolio_name not in STUDENT_PORTFOLIOS:
                    raise ValueError("Choose a valid student portfolio.")
                api_key = str(request_data.get("api_key", ""))
                secret_key = str(request_data.get("secret_key", ""))
                result = verify_paper_credentials(api_key, secret_key)
                with PAPER_CONNECTIONS_LOCK:
                    PAPER_CONNECTIONS[portfolio_name] = (api_key.strip(), secret_key.strip())
                self._send_json(200, result)
                return

            if portfolio_name not in STUDENT_PORTFOLIOS:
                raise ValueError("Choose a valid student portfolio.")
            if not symbol.replace(".", "").replace("-", "").isalnum() or len(symbol) > 10:
                raise ValueError("Enter a valid ticker symbol.")
            action = str(request_data.get("action", "")).upper()
            if action not in {"BUY", "SELL"} or request_data.get("confirmed") is not True:
                self._send_json(400, {"error": "A confirmed BUY or SELL order is required."})
                return
            with PAPER_CONNECTIONS_LOCK:
                credentials = PAPER_CONNECTIONS.get(portfolio_name)
            if not credentials:
                self._send_json(409, {"error": "Connect this student's Alpaca paper account first."})
                return
            portfolio_view = build_portfolio_watchlist(portfolio_name, symbol_focus=symbol)
            if not portfolio_view["watchlist"]:
                self._send_json(409, {"error": f"{symbol} is not held in {portfolio_view['display']}'s configured portfolio."})
                return
            if action == "BUY" and portfolio_view["cash_reserve"] <= 0:
                self._send_json(409, {"error": f"{portfolio_view['display']} has no configured cash reserve."})
                return
            qty = float(request_data.get("qty", 1.0) or 1.0)
            if qty <= 0:
                raise ValueError("Order quantity must be positive.")
            automatic = request_data.get("automatic") is True
            positions = {}
            if automatic or action == "SELL":
                positions = get_positions_for_credentials(credentials[0], credentials[1])
            if action == "SELL":
                position = positions.get(symbol)
                held_qty = float(position.get("qty", 0) or 0) if position else 0
                if held_qty <= 0:
                    self._send_json(409, {"error": f"Cannot sell {symbol}: no long position is held in this student account."})
                    return
                if automatic:
                    qty = held_qty
                elif qty > held_qty:
                    self._send_json(409, {"error": f"Cannot sell {qty:g} {symbol} shares; only {held_qty:g} are held."})
                    return
            if automatic and action == "BUY" and symbol in positions:
                self._send_json(200, {"already_exists": True, "message": f"Auto BUY skipped: {symbol} is already an open position."})
                return
            if automatic or action == "SELL":
                open_orders = get_open_orders_for_credentials(credentials[0], credentials[1])
                existing_order = next((
                    order for order in open_orders
                    if order.get("symbol") == symbol and str(order.get("side", "")).lower() == action.lower()
                ), None)
                if existing_order:
                    if automatic:
                        self._send_json(200, {
                            "already_exists": True,
                            "message": f"Auto {action} skipped: existing {symbol} {action} order is {existing_order.get('status', 'open')}.",
                        })
                        return
                    self._send_json(409, {"error": f"Existing {symbol} {action} order is {existing_order.get('status', 'open')}."})
                    return
            if "qty" not in request_data:
                weight = float(portfolio_view["watchlist"][0].get("weight", 0.0) or 0.0)
                portfolio_value = float(portfolio_view.get("starting_capital", 100000.0) or 100000.0)
                price = 250.0
                qty_for_target = calculate_order_qty_for_weight(weight, portfolio_value, price)
                if qty_for_target > 0:
                    qty = float(qty_for_target)
            result = submit_paper_order_for_credentials(credentials[0], credentials[1], symbol, float(qty), portfolio_name, action=action)
            order = result.get("order") or result.get("server_result", {}).get("order")
            order_source = "automatic" if automatic else "manual"
            self._send_json(200, {"order": order, "signal": f"{order_source} {action}", "portfolio": portfolio_name, "qty": float(qty)})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:
            self._send_json(502, {"error": str(exc)})

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def serve_dashboard(host: str = "127.0.0.1", port: int = 8765) -> None:
    if host != "127.0.0.1":
        raise ValueError("The credential dashboard must bind to 127.0.0.1 only.")
    os.environ["ALPACA_PAPER"] = "true"
    os.environ["DASHBOARD_PAPER_CREDENTIALS_ONLY"] = "true"
    os.environ["DASHBOARD_PAPER_CREDENTIALS_CONFIGURED"] = "false"
    os.environ.pop("ALPACA_API_KEY", None)
    os.environ.pop("ALPACA_SECRET_KEY", None)
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Trading dashboard running at http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard server stopped.")
    finally:
        server.server_close()