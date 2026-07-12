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

## Implemented (2026-07-12)
- Email/password JWT auth (register/login/logout/me) with cookies; admin seeded.
- Real draw scraping (52 Lotto + 52 EuroMillions), stored in Mongo.
- Stats endpoint: hot, cold, overdue, full frequency.
- Statistical prediction (frequency + overdue weighting, 3 sets).
- AI prediction (gpt-5.4) returning 3 sets with reasoning + strategy summary.
- Saved predictions CRUD (per-user).
- Frontend: Landing, Auth, Dashboard (game toggle, stat cards, frequency chart, generators, recent draws), Saved page. Protected routes.
- Tested: 21/21 backend pytest + full frontend flows pass.

## Backlog / Next
- P1: Periodic/admin-triggered data refresh scheduler.
- P1: Pydantic schema for saved-prediction payload; env-driven secure cookie flag.
- P2: Additional games (Thunderball, Set For Life); manual number picker & "check my numbers" against latest draw.
- P2: Prediction accuracy tracking over time; shareable prediction cards.
