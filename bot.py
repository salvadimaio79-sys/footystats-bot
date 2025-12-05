import os
import time
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("footystats")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7912248885:AAFwOdg0rX3weVr6NXzW1adcUorvlRY8LyI")
CHAT_ID = os.getenv("CHAT_ID", "6146221712")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "785e7ea308mshc88fb29d2de2ac7p12a681jsn71d79500bcd9")
RAPIDAPI_HOST = "soccer-football-info.p.rapidapi.com"

AVG_THRESHOLD = float(os.getenv("AVG_THRESHOLD", "2.70"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "180"))

notified_matches = set()

TOP_TEAMS = ["bayern", "barcelona", "real madrid", "atletico", "psg", "manchester city", "liverpool", "chelsea", "arsenal", "tottenham", "manchester united", "dortmund", "leipzig", "napoli", "inter", "milan", "juventus", "roma", "ajax", "benfica", "porto"]

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
        if r.ok:
            logger.info("Telegram OK")
            return True
        return False
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

def get_live_matches():
    try:
        url = f"https://{RAPIDAPI_HOST}/live/full/"
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        params = {"i": "en_US", "f": "json", "e": "no"}
        logger.info("Richiesta live")
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if not r.ok:
            logger.error(f"API error: {r.status_code}")
            return []
        data = r.json()
        raw_events = data.get("result", [])
        live = []
        for match in raw_events:
            try:
                in_play = match.get("in_play", False)
                if not in_play:
                    continue
                team_a = match.get("teamA", {})
                team_b = match.get("teamB", {})
                home = team_a.get("name", "").strip()
                away = team_b.get("name", "").strip()
                if not home or not away:
                    continue
                score_a = team_a.get("score", {})
                score_b = team_b.get("score", {})
                home_score = int(score_a.get("f", 0))
                away_score = int(score_b.get("f", 0))
                timer = match.get("timer", "")
                minute = 0
                if timer and ':' in timer:
                    minute = int(timer.split(':')[0])
                period = ""
                if 44 <= minute <= 47:
                    period = "HT"
                elif minute > 0:
                    period = "LIVE"
                champ = match.get("championship", {})
                league = champ.get("name", "")
                live.append({"home": home, "away": away, "home_score": home_score, "away_score": away_score, "minute": minute, "period": period, "league": league})
            except Exception as e:
                logger.debug(f"Parse error: {e}")
        logger.info(f"Live: {len(live)} match")
        return live
    except Exception as e:
        logger.error(f"API exception: {e}")
        return []

def normalize(name):
    name = "".join(c for c in unicodedata.normalize("NFKD", name or "") if not unicodedata.combining(c))
    name = re.sub(r"[^a-z0-9]+", " ", name.lower())
    return " ".join(name.split())

def is_halftime_00(live):
    return live.get("period") == "HT" and live.get("home_score") == 0 and live.get("away_score") == 0

def is_top_team(team_name):
    norm = normalize(team_name)
    return any(team in norm for team in TOP_TEAMS)

def check_matches():
    logger.info("CHECK")
    live = get_live_matches()
    if not live:
        logger.info("Nessun live")
        return
    found = 0
    for l in live:
        logger.info(f"{l['home']} vs {l['away']} | {l['home_score']}-{l['away_score']} | {l['minute']}' | {l['period']}")
        if not is_halftime_00(l):
            continue
        if not (is_top_team(l["home"]) or is_top_team(l["away"])):
            continue
        key = f"{l['home']}|{l['away']}"
        if key in notified_matches:
            continue
        msg = f"🚨 <b>SEGNALE OVER 1.5 FT</b>\n\n⚽ <b>{l['home']} vs {l['away']}</b>\n🏆 {l['league']}\n📊 Squadra TOP (AVG > 2.70)\n⏱️ <b>INTERVALLO</b> ({l['minute']}') | 1T: <b>0-0</b>\n\n🎯 <b>PUNTA ORA: OVER 1.5 FT</b>\n💡 Quote migliori all'HT!"
        if send_telegram(msg):
            notified_matches.add(key)
            found += 1
            logger.info(f"Notifica: {key}")
    logger.info(f"Opportunita: {found}")

def main():
    logger.info("BOT v4 FIXED")
    send_telegram("🤖 <b>Bot v4 Online</b>\n\n✅ API CORRETTA\n⏱️ Check: <b>180s</b>\n🎯 Squadre TOP\n🔍 Minuto LIVE")
    while True:
        try:
            check_matches()
            logger.info(f"Sleep {CHECK_INTERVAL}s")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            send_telegram("Bot arrestato")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
