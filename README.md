# RateLy

Multilingual Telegram bot for live prices, charts, conversion, watchlists, alerts, top movers, anonymous support, and admin tools.

## Files
- main.py
- requirements.txt
- render.yaml
- README.md

## Recommended Render env vars
- BOT_TOKEN
- BOT_USERNAME
- BOT_NAME
- ADMIN_IDS
- DEFAULT_LANG=en
- ADS_TEXT
- ADS_EVERY
- APP_TITLE
- PYTHON_VERSION=3.11.9

## Notes
- The bot uses Nobitex public market stats for Iranian crypto pricing when possible.
- It uses CoinGecko bulk market data for movers and crypto lookup.
- It uses open.er-api for fiat FX conversion.
- Set BotFather privacy mode OFF to read normal group messages.
