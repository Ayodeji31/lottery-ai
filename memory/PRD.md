# LottoLuck AI — Product Requirements Document

## Original Problem Statement
"Build me an app that predicts national lottery and euro millions."

## User Choices
- Games: UK National Lottery (Lotto) + EuroMillions
- Predictions: Both statistical + AI
- Data: Fetch real historical draw data
- Auth: Email + password (JWT)
- Design: Sky blue, modern, mobile-friendly

## Architecture
- **Frontend**: React 19 (CRA/craco), Tailwind, shadcn/ui, framer-motion, recharts. Dark "Crystal Sky" theme (Outfit/Manrope/JetBrains Mono fonts).
- **Backend**: FastAPI. Modules: `auth.py` (JWT httpOnly-cookie auth), `lottery.py` (data scrape + stats + AI + saved), `server.py` (app/routers/CORS/startup).
- **DB**: MongoDB (`draws`, `users`, `saved_predictions`).
- **Data source**: Scrapes ~52 real recent draws per game from lottery.co.uk/{game}/results/past on startup.
- **AI**: emergentintegrations LlmChat (OpenAI gpt-5.4) via Emergent LLM key; graceful fallback to statistical if LLM fails.

## User Personas
- Casual UK lottery players wanting data-driven number suggestions (entertainment).

## Core Requirements (static)
- Real historical draws for Lotto & EuroMillions
- Statistical analysis (hot/cold/overdue/frequency)
- Statistical + AI prediction generators
- Account-gated predictions, saved predictions
- Responsible-gambling disclaimers

## Implemented (2026-07-12/13)
- Email/password JWT auth (register/login/logout/me) with cookies + Bearer token (localStorage) for mobile/webview resilience; admin seeded.
- Real draw scraping (52 Lotto + 52 EuroMillions), stored in Mongo.
- Stats endpoint: hot, cold, overdue, full frequency.
- Statistical prediction (frequency + overdue weighting, 3 sets).
- AI prediction (gpt-5.4) returning 3 sets with reasoning + strategy summary; graceful statistical fallback.
- Saved predictions CRUD (per-user, limit 100).
- Frontend: Landing, Auth (password eye toggle), Dashboard (game toggle, stat cards, frequency chart, generators, recent draws), Saved page. Protected routes.
- PWA: manifest + service worker + icons (installable, mobile-optimized).
- Resilience: axios auto-retry on transient/cold-start failures (network/502/503/504).
- **Monetization (Freemium + Stripe TEST mode):** Free = UK Lotto + 1 AI prediction/day; Pro (£4.99/mo) = all games + unlimited AI + accuracy tracker (tracker pending). Stripe Checkout via emergentintegrations; payment_transactions collection (idempotent); user.pro_until drives is_pro. Backend gating (402 upsell) on EuroMillions predictions & AI daily quota. Upgrade page, Go Pro/Pro badge in nav, payment-return polling.
- Tested: 42/42 backend pytest + full paid Stripe flow + all frontend flows pass.
- **Accuracy Tracker (Pro):** `/api/accuracy` backtests saved sets vs real historical draws → best match, prize tier, hit rate. `/accuracy` page (Pro-gated upsell for free).
- **Auto draw-refresh + prize notifications:** data source now beatlottery.co.uk (primary) + lottery.co.uk (fallback); `refresh_game` upserts draws (never shrinks history, keeps real data on scrape failure, no sample pollution). 6h background scheduler + admin `/api/admin/refresh-now`. On a genuinely new draw, Pro users whose saved set hits a tier get a "You would have won" notification (dedup by user+prediction+draw). Nav bell + badge + panel (`/api/notifications`).
- Tested: 64/64 backend pytest + full notification/accuracy flows pass.

## Backlog / Next
- P1: Real recurring subscription (Stripe Billing) + "Manage/Cancel subscription" + auto-renew; currently each payment grants 30 days.
- P1: Tighten CORS_ORIGINS to explicit prod domain.
- P2: Additional games (Thunderball, Set For Life); manual number picker & "check my numbers"; shareable prediction cards; syndicate/group-play manager.
- P2: Forward-looking accuracy (auto re-scrape new draws + track predictions made before each draw), on top of current backtest.
