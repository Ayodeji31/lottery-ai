import os
import re
import json
import uuid
import random
import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone

import requests
from typing import List
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from auth import db, get_current_user, user_is_pro
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)
lottery_router = APIRouter(prefix="/api", tags=["lottery"])
REFRESH_INTERVAL_HOURS = 6

GAMES = {
    "lotto": {
        "name": "UK National Lottery",
        "url": "https://www.lottery.co.uk/lotto/results/past",
        "main_cls": "lotto-ball",
        "bonus_cls": "lotto-bonus-ball",
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


BL = {
    "lotto": {"slug": "lotto", "main": "ball-lotto", "bonus": "ball-bonus"},
    "euromillions": {"slug": "euromillions", "main": "ball-euromillions",
                     "bonus": "ball-euromillions-lucky-star"},
}
BL_TOKEN = re.compile(
    r'<span\s+class="results_ball_new([^"]*)">\s*(\d{1,2})\s*</span>'
    r'|/(?:lotto|euromillions)/results/draw_date/(\d{4}-\d{2}-\d{2})'
)


def _parse_beatlottery(html: str, game: str):
    cfg = GAMES[game]
    bl = BL[game]
    results, cur_main, cur_bonus = [], [], []
    for m in BL_TOKEN.finditer(html):
        classes, num, date = m.group(1), m.group(2), m.group(3)
        if date is not None:
            if len(cur_main) >= cfg["main_count"]:
                results.append({
                    "game": game,
                    "draw_number": date.replace("-", ""),
                    "draw_date": date,
                    "main_numbers": cur_main[: cfg["main_count"]],
                    "bonus_numbers": cur_bonus[: cfg["bonus_count"]],
                })
            cur_main, cur_bonus = [], []
        elif num is not None:
            n = int(num)
            if bl["bonus"] in classes:
                cur_bonus.append(n)
            elif bl["main"] in classes:
                cur_main.append(n)
    return results


def _scrape_game(game: str):
    """Primary: beatlottery.co.uk year pages. Fallback: lottery.co.uk."""
    cfg = GAMES[game]
    year = datetime.now(timezone.utc).year
    draws = []
    for y in (year, year - 1):
        url = f"https://www.beatlottery.co.uk/{BL[game]['slug']}/draw-history/year/{y}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            r.raise_for_status()
            draws += _parse_beatlottery(r.text, game)
        except Exception as e:
            logger.warning(f"beatlottery {game} {y} failed: {e}")
        if len(draws) >= 60:
            break
    if draws:
        seen, unique = set(), []
        for d in draws:
            if d["draw_number"] not in seen:
                seen.add(d["draw_number"])
                unique.append(d)
        return unique
    try:
        r = requests.get(cfg["url"], headers=HEADERS, timeout=25)
        r.raise_for_status()
        return _parse_results_html(r.text, game, cfg)
    except Exception as e:
        logger.warning(f"lottery.co.uk {game} fallback failed: {e}")
    return []


async def refresh_game(game: str):
    parsed = _scrape_game(game)

    existing = await db.draws.find({"game": game}, {"draw_number": 1, "_id": 0}).to_list(length=None)
    existing_numbers = {d["draw_number"] for d in existing}

    if not parsed:
        # Scrape failed: keep real data if we have it; only seed sample into an empty DB.
        if existing_numbers:
            logger.warning(f"Scrape failed for {game}; keeping {len(existing_numbers)} existing draws")
            return []
        logger.warning(f"Seeding generated sample data for {game} (empty DB)")
        await db.draws.insert_many([{**d} for d in _generate_sample(game)])
        return []

    new_draws = [d for d in parsed if d["draw_number"] not in existing_numbers]
    await db.draws.delete_many({"game": game})
    await db.draws.insert_many([{**d} for d in parsed])
    return new_draws


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


async def _notify_new_draw(game: str, draw: dict) -> int:
    """Create 'you won a prize' notifications for Pro users whose saved sets hit a tier."""
    created = 0
    cfg = GAMES[game]
    saved = await db.saved_predictions.find({"game": game}).to_list(length=None)
    pro_cache = {}
    for pred in saved:
        uid = pred["user_id"]
        if uid not in pro_cache:
            try:
                u = await db.users.find_one({"_id": ObjectId(uid)})
            except Exception:
                u = None
            pro_cache[uid] = bool(u) and user_is_pro(u)
        if not pro_cache[uid]:
            continue
        m = len(set(pred.get("main_numbers", [])) & set(draw["main_numbers"]))
        b = len(set(pred.get("bonus_numbers", [])) & set(draw.get("bonus_numbers", [])))
        prize = _prize_tier(game, m, b)
        if not prize:
            continue
        dedup = {"user_id": uid, "prediction_id": pred["id"], "draw_number": draw["draw_number"]}
        if await db.notifications.find_one(dedup):
            continue
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "prediction_id": pred["id"],
            "type": "prize",
            "game": game,
            "draw_number": draw["draw_number"],
            "draw_date": draw["draw_date"],
            "prize": prize,
            "main_matched": m,
            "bonus_matched": b,
            "title": f"You would have won — {prize}!",
            "body": f"Your saved {cfg['name']} set matched {m} number{'s' if m != 1 else ''}"
                    + (f" + {b} bonus" if b else "") + f" in the {draw['draw_date']} draw.",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        created += 1
    return created


async def refresh_and_notify():
    total_new, total_notif = 0, 0
    for game in GAMES:
        new_draws = await refresh_game(game)
        for d in new_draws:
            total_notif += await _notify_new_draw(game, d)
        total_new += len(new_draws)
    await db.meta.update_one(
        {"_id": "draws"},
        {"$set": {"last_refresh": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    logger.info(f"refresh_and_notify: {total_new} new draws, {total_notif} notifications")
    return total_new, total_notif


async def refresh_scheduler():
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_HOURS * 3600)
        try:
            await refresh_and_notify()
        except Exception:
            logger.warning("Scheduled refresh failed", exc_info=True)


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
async def refresh(game: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if game not in GAMES:
        raise HTTPException(status_code=404, detail="Unknown game")
    new_draws = await refresh_game(game)
    notif = 0
    for d in new_draws:
        notif += await _notify_new_draw(game, d)
    return {"game": game, "new_draws": len(new_draws), "notifications_created": notif}


@lottery_router.post("/admin/refresh-now")
async def admin_refresh_now(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    total_new, total_notif = await refresh_and_notify()
    return {"new_draws": total_new, "notifications_created": total_notif}


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


FREE_GAME = "lotto"
FREE_AI_DAILY_LIMIT = 1


def _require_game_access(game: str, user: dict):
    if game != FREE_GAME and not user_is_pro(user):
        raise HTTPException(
            status_code=402,
            detail="EuroMillions predictions are a Pro feature. Upgrade to unlock all games.",
        )


async def _enforce_ai_quota(user: dict):
    if user_is_pro(user):
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = user.get("ai_usage") or {}
    count = usage.get("count", 0) if usage.get("date") == today else 0
    if count >= FREE_AI_DAILY_LIMIT:
        raise HTTPException(
            status_code=402,
            detail="You've used your free AI prediction for today. Upgrade to Pro for unlimited AI predictions.",
        )
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"ai_usage": {"date": today, "count": count + 1}}},
    )


@lottery_router.post("/predict/statistical/{game}")
async def predict_statistical(game: str, user: dict = Depends(get_current_user)):
    if game not in GAMES:
        raise HTTPException(status_code=404, detail="Unknown game")
    _require_game_access(game, user)
    await ensure_data()
    draws_list = await _get_draws(game)
    stats_data = compute_stats(draws_list, GAMES[game])
    preds = statistical_prediction(stats_data, GAMES[game], sets=3)
    return {"method": "statistical", "game": game, "predictions": preds}


AI_SYSTEM = (
    "You are a lottery statistics analyst. You know lottery draws are random and "
    "cannot be truly predicted, but you provide statistically-informed number suggestions "
    "for entertainment. Always respond with STRICT JSON only, no markdown."
)


def _build_ai_prompt(cfg, stats_data, draws_list):
    hot = [h["number"] for h in stats_data["hot"]]
    cold = [c["number"] for c in stats_data["cold"]]
    overdue = [o["number"] for o in stats_data["overdue"]]
    recent = [d["main_numbers"] for d in draws_list[:8]]
    return f"""Game: {cfg['name']}
Rules: pick {cfg['main_count']} main numbers from 1-{cfg['main_max']} and {cfg['bonus_count']} {cfg['bonus_label']} from 1-{cfg['bonus_max']}.
Historical analysis over {stats_data['total_draws']} draws:
- Hot numbers (most frequent): {hot}
- Cold numbers (least frequent): {cold}
- Overdue numbers (not drawn recently): {overdue}
- Recent 8 draws main numbers: {recent}

Generate 3 distinct suggested number sets balancing hot and overdue numbers.
Respond in this exact JSON schema:
{{"predictions":[{{"main_numbers":[...],"bonus_numbers":[...],"reasoning":"one short sentence"}}],"summary":"2 sentence overview of the strategy"}}"""


async def _call_ai(game, prompt):
    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=f"predict-{game}-{uuid.uuid4()}",
        system_message=AI_SYSTEM,
    ).with_model("openai", "gpt-5.4")
    reply = (await chat.send_message(UserMessage(text=prompt))).strip()
    if reply.startswith("```"):
        reply = reply.split("```")[1]
        if reply.startswith("json"):
            reply = reply[4:]
    return json.loads(reply)


def _ai_fallback(stats_data, cfg):
    preds = statistical_prediction(stats_data, cfg, sets=3)
    for p in preds:
        p["reasoning"] = "Balanced blend of hot and overdue numbers."
    return {"predictions": preds, "summary": "Statistical fallback based on frequency and overdue analysis."}


def _sanitize_predictions(data, cfg):
    for p in data.get("predictions", []):
        p["main_numbers"] = sorted(list(dict.fromkeys(p.get("main_numbers", [])))[: cfg["main_count"]])
        p["bonus_numbers"] = sorted(list(dict.fromkeys(p.get("bonus_numbers", [])))[: cfg["bonus_count"]])
    return data


@lottery_router.post("/predict/ai/{game}")
async def predict_ai(game: str, user: dict = Depends(get_current_user)):
    if game not in GAMES:
        raise HTTPException(status_code=404, detail="Unknown game")
    _require_game_access(game, user)
    await _enforce_ai_quota(user)
    await ensure_data()
    cfg = GAMES[game]
    draws_list = await _get_draws(game)
    stats_data = compute_stats(draws_list, cfg)
    prompt = _build_ai_prompt(cfg, stats_data, draws_list)
    try:
        data = await _call_ai(game, prompt)
    except Exception:
        logger.warning("AI prediction failed, using fallback", exc_info=True)
        data = _ai_fallback(stats_data, cfg)
    data = _sanitize_predictions(data, cfg)
    return {"method": "ai", "game": game, **data}


# ---------- Saved predictions ----------
class SavedPredictionInput(BaseModel):
    game: str
    method: str = "manual"
    main_numbers: List[int] = []
    bonus_numbers: List[int] = []
    reasoning: str = ""


@lottery_router.post("/saved")
async def save_prediction(payload: SavedPredictionInput, user: dict = Depends(get_current_user)):
    if payload.game not in GAMES:
        raise HTTPException(status_code=400, detail="Unknown game")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": str(user["_id"]),
        "game": payload.game,
        "method": payload.method,
        "main_numbers": payload.main_numbers,
        "bonus_numbers": payload.bonus_numbers,
        "reasoning": payload.reasoning,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.saved_predictions.insert_one({**doc})
    return doc


@lottery_router.get("/saved")
async def list_saved(user: dict = Depends(get_current_user)):
    items = await db.saved_predictions.find(
        {"user_id": str(user["_id"])}, {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(length=100)
    return items


@lottery_router.delete("/saved/{pred_id}")
async def delete_saved(pred_id: str, user: dict = Depends(get_current_user)):
    res = await db.saved_predictions.delete_one({"id": pred_id, "user_id": str(user["_id"])})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"message": "Deleted"}


# ---------- Accuracy tracker (Pro) ----------
def _prize_tier(game: str, main_matched: int, bonus_matched: int):
    """Return a prize label if the match qualifies for a prize, else None."""
    if game == "lotto":
        if main_matched == 6:
            return "Jackpot"
        if main_matched == 5 and bonus_matched >= 1:
            return "Match 5 + Bonus"
        if main_matched == 5:
            return "Match 5"
        if main_matched == 4:
            return "Match 4"
        if main_matched == 3:
            return "Match 3"
        if main_matched == 2:
            return "Match 2 (Lucky Dip)"
        return None
    # euromillions (simplified tiers; minimum prize = 2 main, or 1 main + 2 stars)
    if main_matched == 5 and bonus_matched == 2:
        return "Jackpot"
    if main_matched >= 2 or (main_matched == 1 and bonus_matched == 2) or (main_matched == 0 and bonus_matched == 2):
        label = f"Match {main_matched}"
        if bonus_matched:
            label += f" + {bonus_matched} Star{'s' if bonus_matched > 1 else ''}"
        return label
    return None


def _evaluate_prediction(pred: dict, draws: list):
    main_set = set(pred.get("main_numbers", []))
    bonus_set = set(pred.get("bonus_numbers", []))
    best = None
    prize_hits = 0
    for d in draws:
        m = len(main_set & set(d["main_numbers"]))
        b = len(bonus_set & set(d.get("bonus_numbers", [])))
        prize = _prize_tier(pred["game"], m, b)
        if prize:
            prize_hits += 1
        score = m * 10 + b
        if best is None or score > best["_score"]:
            best = {
                "_score": score,
                "main_matched": m,
                "bonus_matched": b,
                "draw_date": d["draw_date"],
                "draw_main": d["main_numbers"],
                "draw_bonus": d.get("bonus_numbers", []),
                "prize": prize,
            }
    if best:
        best.pop("_score", None)
    return {"draws_checked": len(draws), "best": best, "prize_hits": prize_hits}


@lottery_router.get("/accuracy")
async def accuracy(user: dict = Depends(get_current_user)):
    if not user_is_pro(user):
        raise HTTPException(
            status_code=402,
            detail="The accuracy tracker is a Pro feature. Upgrade to see how your sets perform.",
        )
    await ensure_data()
    saved = await db.saved_predictions.find(
        {"user_id": str(user["_id"])}, {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(length=100)

    draws_cache = {}
    results = []
    total_draws_checked = 0
    total_prize_hits = 0
    best_ever = None
    for pred in saved:
        game = pred["game"]
        if game not in draws_cache:
            draws_cache[game] = await _get_draws(game)
        ev = _evaluate_prediction(pred, draws_cache[game])
        total_draws_checked += ev["draws_checked"]
        total_prize_hits += ev["prize_hits"]
        entry = {
            "id": pred["id"],
            "game": game,
            "method": pred.get("method", "manual"),
            "main_numbers": pred.get("main_numbers", []),
            "bonus_numbers": pred.get("bonus_numbers", []),
            "created_at": pred.get("created_at"),
            **ev,
        }
        results.append(entry)
        if ev["best"] and (best_ever is None or (ev["best"]["main_matched"] * 10 + ev["best"]["bonus_matched"]) >
                           (best_ever["main_matched"] * 10 + best_ever["bonus_matched"])):
            best_ever = {**ev["best"], "game": game}

    hit_rate = round(total_prize_hits / total_draws_checked * 100, 1) if total_draws_checked else 0
    summary = {
        "tracked": len(saved),
        "total_draws_checked": total_draws_checked,
        "total_prize_hits": total_prize_hits,
        "hit_rate": hit_rate,
        "best_ever": best_ever,
    }
    return {"summary": summary, "predictions": results}


# ---------- Notifications ----------
@lottery_router.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    uid = str(user["_id"])
    items = await db.notifications.find(
        {"user_id": uid}, {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(length=50)
    unread = await db.notifications.count_documents({"user_id": uid, "read": False})
    return {"unread_count": unread, "notifications": items}


@lottery_router.post("/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str, user: dict = Depends(get_current_user)):
    res = await db.notifications.update_one(
        {"id": notif_id, "user_id": str(user["_id"])}, {"$set": {"read": True}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"message": "ok"}


@lottery_router.post("/notifications/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.notifications.update_many(
        {"user_id": str(user["_id"]), "read": False}, {"$set": {"read": True}}
    )
    return {"message": "ok"}

