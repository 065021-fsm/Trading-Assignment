# Trading Project Scaffold

This repository is intentionally kept lightweight while preserving the required project structure and simple run paths.

## Current status
- Phase 0: completed with MCP server contracts and starter validation.
- Phase 1: scaffolded with config, environment files, and LLM startup checks.

## Project layout
- [mcp_servers](mcp_servers)
- [starter](starter)
- [config](config)
- [core](core)
- [.env.example](.env.example)
- [.env](.env)

## Quick setup
1. Fill in [.env](.env) with your Alpaca and LLM values.
2. Run the startup test:

   python -m core.llm --test

3. Test the demo order paths:

   python mcp_servers/stock_trading/trading_crew.py --mode single --symbol TSLA
   python mcp_servers/alpaca/order_client.py TSLA 1 --dry-run

## Notes
- This version uses a minimal deterministic fallback to avoid brittle tool installation issues in the current environment.
- The project remains compatible with the bigger design described in the master prompt, but the code here is deliberately simpler and easier to debug.
