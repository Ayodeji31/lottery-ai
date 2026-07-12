import os
import re
import json
import uuid
import random
import logging
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, HTTPException, Depends, Query

from auth import db, get_current_user
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)
lottery_router = APIRouter(prefix="/api", tags=["lottery"])

GAMES = {
    "lotto": {
        "name": "UK National Lottery",
        "url": "https://www.lottery.co.uk/lotto/results/past",
        "main_cls": "lotto-ball-round-1",
        "bonus_cls": "lotto-bonus-ball-round-1",
        "main_count": 6,
        "main_max": 59,
        "bonus_count": 1,
        "bonus_max": 59,
        "bonus_label": "Bonus Ball",
    },
    "euromillions": {
        "name": "EuroMillions",
        "url": "https://www.lottery.co.uk/euromillions/results/past",
        "main_cls": "euromillions-ball",
        "bonus_cls": "euromillions-lucky-star",
        "main_count": 5,
        "main_max": 50,
        "bonus_count": 2,
        "bonus_max": 12,
        "bonus_label": "Lucky Stars",
    },
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _parse_results_html(html: str, game: str, cfg: dict):
    """Scrape lottery.co.uk past-results page into normalized draws."""
    slug = "lotto" if game == "lotto" else "euromillions"
    row_re = re.compile(
        r'href="/' + slug + r'/results-(\d{2})-(\d{2})-(\d{4})"[^>]*class="smallerHeading'
    )
    main_re = re.compile(
        r'class="result small ' + cfg["main_cls"] + r'[^"]*">(\d+)</div>'
    )
    bonus_re = re.compile(
        r'class="result small ' + cfg["bonus_cls"] + r'[^"]*">(\d+)</div>'
    )
    matches = list(row_re.finditer(html))
    results = []
    for i, m in enumerate(matches):
        d, mo, y = m.groups()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        seg = html[m.end():end]
        main = [int(x) for x in main_re.findall(seg)][: cfg["main_count"]]
        bonus = [int(x) for x in bonus_re.findall(seg)][: cfg["bonus_count"]]
        if len(main) == cfg["main_count"]:
            results.append({
                "game": game,
                "draw_number": f"{y}{mo}{d}",
                "draw_date": f"{y}-{mo}-{d}",
                "main_numbers": main,
                "bonus_numbers": bonus,
            })
    return results


def _generate_sample(game: str, count: int = 200):
    cfg = GAMES[game]
    draws = []
    base = datetime.now(timezone.utc)
    for i in range(count):
        main = sorted(random.sample(range(1, cfg["main_max"] + 1), cfg["main_count"]))
        bonus = sorted(random.sample(range(1, cfg["bonus_max"] + 1), cfg["bonus_count"]))
        draws.append({
            "game": game,
            "draw_number": str(3000 - i if game == "lotto" else 1900 - i),
            "draw_date": (base).strftime("%Y-%m-%d"),
            "main_numbers": main,
            "bonus_numbers": bonus,
            "sample": True,
        })
    return draws


async def refresh_game(game: str):
    cfg = GAMES[game]
    parsed = []
    try:
        resp = requests.get(cfg["url"], headers=HEADERS, timeout=25)
        resp.raise_for_status()
        parsed = _parse_results_html(resp.text, game, cfg)
    except Exception as e:
        logger.warning(f"Failed to fetch {game} data: {e}")
    if not parsed:
        logger.warning(f"Using generated sample data for {game}")
        parsed = _generate_sample(game)
    await db.draws.delete_many({"game": game})
    if parsed:
        await db.draws.insert_many([{**d} for d in parsed])
    return len(parsed)


async def ensure_data():
    for game in GAMES:
        existing = await db.draws.count_documents({"game": game})
        if existing == 0:
            await refresh_game(game)


async def _get_draws(game: str, limit: int = 0):
    cursor = db.draws.find({"game": game}, {"_id": 0}).sort("draw_number", -1)
    if limit:
        cursor = cursor.limit(limit)
    return await cursor.to_list(length=None)


def compute_stats(draws, cfg):
    main_counter = Counter()
    bonus_counter = Counter()
    last_seen = {}
    for idx, d in enumerate(draws):  # draws sorted newest first
        for n in d["main_numbers"]:
            main_counter[n] += 1
            if n not in last_seen:
                last_seen[n] = idx
        for n in d.get("bonus_numbers", []):
            bonus_counter[n] += 1

    total = len(draws)
    main_freq = []
    for n in range(1, cfg["main_max"] + 1):
        c = main_counter.get(n, 0)
        main_freq.append({
            "number": n,
            "count": c,
            "percentage": round(c / total * 100, 1) if total else 0,
            "draws_ago": last_seen.get(n, total),
        })
    bonus_freq = []
    for n in range(1, cfg["bonus_max"] + 1):
        c = bonus_counter.get(n, 0)
        bonus_freq.append({
            "number": n,
            "count": c,
            "percentage": round(c / total * 100, 1) if total else 0,
        })

    by_count = sorted(main_freq, key=lambda x: x["count"], reverse=True)
    by_overdue = sorted(main_freq, key=lambda x: x["draws_ago"], reverse=True)
    return {
        "total_draws": total,
        "main_frequency": main_freq,
        "bonus_frequency": bonus_freq,
        "hot": by_count[:6],
        "cold": by_count[-6:][::-1],
        "overdue": by_overdue[:6],
    }


@lottery_router.post("/refresh/{game}")
async def refresh(game: str):
    if game not in GAMES:
        raise HTTPException(status_code=404, detail="Unknown game")
    count = await refresh_game(game)
    return {"game": game, "draws_loaded": count}


@lottery_router.get("/games")
async def get_games():
    return [{"id": k, **{x: v[x] for x in ["name", "main_count", "main_max", "bonus_count", "bonus_max", "bonus_label"]}} for k, v in GAMES.items()]


@lottery_router.get("/draws/{game}")
async def draws(game: str, limit: int = Query(20, le=200)):
    if game not in GAMES:
        raise HTTPException(status_code=404, detail="Unknown game")
    await ensure_data()
    return await _get_draws(game, limit)


@lottery_router.get("/stats/{game}")
async def stats(game: str):
    if game not in GAMES:
        raise HTTPException(status_code=404, detail="Unknown game")
    await ensure_data()
    draws_list = await _get_draws(game)
    return compute_stats(draws_list, GAMES[game])


def statistical_prediction(stats_data, cfg, sets=1):
    """Weighted pick blending hot & overdue numbers."""
    freq = stats_data["main_frequency"]
    weights = {}
    for f in freq:
        w = f["count"] + 1 + (f["draws_ago"] * 0.15)
        weights[f["number"]] = w
    predictions = []
    for _ in range(sets):
        pool = list(weights.keys())
        wl = [weights[n] for n in pool]
        chosen = set()
        while len(chosen) < cfg["main_count"]:
            pick = random.choices(pool, weights=wl, k=1)[0]
            chosen.add(pick)
        bonus = sorted(random.sample(range(1, cfg["bonus_max"] + 1), cfg["bonus_count"]))
        predictions.append({"main_numbers": sorted(chosen), "bonus_numbers": bonus})
    return predictions


@lottery_router.post("/predict/statistical/{game}")
async def predict_statistical(game: str, user: dict = Depends(get_current_user)):
    if game not in GAMES:
        raise HTTPException(status_code=404, detail="Unknown game")
    await ensure_data()
    draws_list = await _get_draws(game)
    stats_data = compute_stats(draws_list, GAMES[game])
    preds = statistical_prediction(stats_data, GAMES[game], sets=3)
    return {"method": "statistical", "game": game, "predictions": preds}


@lottery_router.post("/predict/ai/{game}")
async def predict_ai(game: str, user: dict = Depends(get_current_user)):
    if game not in GAMES:
        raise HTTPException(status_code=404, detail="Unknown game")
    await ensure_data()
    cfg = GAMES[game]
    draws_list = await _get_draws(game)
    stats_data = compute_stats(draws_list, cfg)

    hot = [h["number"] for h in stats_data["hot"]]
    cold = [c["number"] for c in stats_data["cold"]]
    overdue = [o["number"] for o in stats_data["overdue"]]
    recent = [d["main_numbers"] for d in draws_list[:8]]

    system = (
        "You are a lottery statistics analyst. You know lottery draws are random and "
        "cannot be truly predicted, but you provide statistically-informed number suggestions "
        "for entertainment. Always respond with STRICT JSON only, no markdown."
    )
    prompt = f"""Game: {cfg['name']}
Rules: pick {cfg['main_count']} main numbers from 1-{cfg['main_max']} and {cfg['bonus_count']} {cfg['bonus_label']} from 1-{cfg['bonus_max']}.
Historical analysis over {stats_data['total_draws']} draws:
- Hot numbers (most frequent): {hot}
- Cold numbers (least frequent): {cold}
- Overdue numbers (not drawn recently): {overdue}
- Recent 8 draws main numbers: {recent}

Generate 3 distinct suggested number sets balancing hot and overdue numbers.
Respond in this exact JSON schema:
{{"predictions":[{{"main_numbers":[...],"bonus_numbers":[...],"reasoning":"one short sentence"}}],"summary":"2 sentence overview of the strategy"}}"""

    try:
        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"predict-{game}-{uuid.uuid4()}",
            system_message=system,
        ).with_model("openai", "gpt-5.4")
        reply = await chat.send_message(UserMessage(text=prompt))
        text = reply.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
    except Exception as e:
        logger.warning(f"AI prediction failed, using fallback: {e}")
        preds = statistical_prediction(stats_data, cfg, sets=3)
        for p in preds:
            p["reasoning"] = "Balanced blend of hot and overdue numbers."
        data = {"predictions": preds, "summary": "Statistical fallback based on frequency and overdue analysis."}

    # sanitize
    for p in data.get("predictions", []):
        p["main_numbers"] = sorted(list(dict.fromkeys(p.get("main_numbers", [])))[:cfg["main_count"]])
        p["bonus_numbers"] = sorted(list(dict.fromkeys(p.get("bonus_numbers", [])))[:cfg["bonus_count"]])
    return {"method": "ai", "game": game, **data}


# ---------- Saved predictions ----------
@lottery_router.post("/saved")
async def save_prediction(payload: dict, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": str(user["_id"]),
        "game": payload.get("game"),
        "method": payload.get("method", "manual"),
        "main_numbers": payload.get("main_numbers", []),
        "bonus_numbers": payload.get("bonus_numbers", []),
        "reasoning": payload.get("reasoning", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.saved_predictions.insert_one({**doc})
    return doc


@lottery_router.get("/saved")
async def list_saved(user: dict = Depends(get_current_user)):
    items = await db.saved_predictions.find(
        {"user_id": str(user["_id"])}, {"_id": 0}
    ).sort("created_at", -1).to_list(length=None)
    return items


@lottery_router.delete("/saved/{pred_id}")
async def delete_saved(pred_id: str, user: dict = Depends(get_current_user)):
    res = await db.saved_predictions.delete_one({"id": pred_id, "user_id": str(user["_id"])})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"message": "Deleted"}
