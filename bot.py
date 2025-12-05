import os
import time
import re
import unicodedata
from datetime import datetime
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("footystats")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7912248885:AAFwOdg0rX3weVr6NXzW1adcUorvlRY8LyI")
CHAT_ID = os.getenv("CHAT_ID", "6146221712")
FOOTYSTATS_API_KEY = os.getenv("FOOTYSTATS_API_KEY", "59c0b4d0f445de0323f7e98880350ed6c583d74907ae64b9b59cfde6a09dd811")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "785e7ea308mshc88fb29d2de2ac7p12a681jsn71d79500bcd9")
RAPIDAPI_HOST = "soccer-football-info.p.rapidapi.com"

AVG_THRESHOLD = float(os.getenv("AVG_THRESHOLD", "2.70"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "180"))
FOOTYSTATS_REFRESH = int(os.getenv("FOOTYSTATS_REFRESH", "1800"))

notified_matches = set()
footystats_data = {}
last_footystats_update = 0

def normalize(name):
    name = "".join(c for c in unicodedata.normalize("NFKD", name or "") if not unicodedata.combining(c))
    name = re.sub(r"[^a-z0-9]+", " ", name.lower())
    return " ".join(name.split())

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

def get_footystats_matches():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = "https://api.football-data-api.com/todays-matches"
        params = {"key": FOOTYSTATS_API_KEY, "date": today}
        
        logger.info(f"FootyStats: richiesta {today}")
        r = requests.get(url, params=params, timeout=30)
        
        if not r.ok:
            logger.error(f"FootyStats: {r.status_code}")
            return {}
        
        data = r.json()
        matches = data.get("data", [])
        logger.info(f"FootyStats: {len(matches)} match totali")
        
        high_avg = {}
        
        for m in matches:
            try:
                home = m.get("home_name", "").strip()
                away = m.get("away_name", "").strip()
                
                if not home or not away:
                    continue
                
                stats = m.get("stats", {})
                avg = float(stats.get("avg_potential", {}).get("home", 0))
                
                if avg == 0:
                    avg_h = float(stats.get("avg_goals_per_match_home", 0))
                    avg_a = float(stats.get("avg_goals_per_match_away", 0))
                    if avg_h > 0 and avg_a > 0:
                        avg = (avg_h + avg_a) / 2
                
                if avg >= AVG_THRESHOLD:
                    key = f"{normalize(home)}|{normalize(away)}"
                    high_avg[key] = {
                        "home": home,
                        "away": away,
                        "avg": avg,
                        "league": m.get("competition", {}).get("name", "")
                    }
            except Exception as e:
                logger.debug(f"Parse: {e}")
        
        logger.info(f"FootyStats: {len(high_avg)} match AVG>={AVG_THRESHOLD}")
        return high_avg
        
    except Exception as e:
        logger.error(f"FootyStats error: {e}")
        return {}

def get_live_matches():
    try:
        url = f"https://{RAPIDAPI_HOST}/live/full/"
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        params = {"i": "en_US", "f": "json", "e": "no"}
        
        logger.info("Bet365: richiesta live")
        r = requests.get(url, headers=headers, params=params, timeout=20)
        
        if not r.ok:
            logger.error(f"Bet365: {r.status_code}")
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
                
                key = f"{normalize(home)}|{normalize(away)}"
                
                live.append({
                    "home": home,
                    "away": away,
                    "home_score": home_score,
                    "away_score": away_score,
                    "minute": minute,
                    "period": period,
                    "league": league,
                    "key": key
                })
            except Exception as e:
                logger.debug(f"Parse: {e}")
        
        logger.info(f"Bet365: {len(live)} match live")
        return live
        
    except Exception as e:
        logger.error(f"Bet365 error: {e}")
        return []

def is_halftime_00(match):
    return match.get("period") == "HT" and match.get("home_score") == 0 and match.get("away_score") == 0

def check_matches():
    global footystats_data, last_footystats_update
    
    now = time.time()
    
    if now - last_footystats_update > FOOTYSTATS_REFRESH:
        logger.info("Aggiorno FootyStats...")
        footystats_data = get_footystats_matches()
        last_footystats_update = now
    
    if not footystats_data:
        logger.info("Nessun match AVG alto")
        return
    
    live = get_live_matches()
    if not live:
        logger.info("Nessun live")
        return
    
    found = 0
    
    for l in live:
        if not is_halftime_00(l):
            continue
        
        key = l["key"]
        
        if key not in footystats_data:
            continue
        
        if key in notified_matches:
            continue
        
        fs = footystats_data[key]
        
        msg = (
            f"🚨 <b>SEGNALE OVER 1.5 FT</b>\n\n"
            f"⚽ <b>{l['home']} vs {l['away']}</b>\n"
            f"🏆 {l['league']}\n"
            f"📊 AVG FootyStats: <b>{fs['avg']:.2f}</b>\n"
            f"⏱️ <b>INTERVALLO</b> ({l['minute']}') | 1T: <b>0-0</b>\n\n"
            f"🎯 <b>PUNTA ORA: OVER 1.5 FT</b>\n"
            f"💡 Quote migliori all'HT!"
        )
        
        if send_telegram(msg):
            notified_matches.add(key)
            found += 1
            logger.info(f"NOTIFICA: {fs['home']} vs {fs['away']} | AVG {fs['avg']:.2f}")
    
    logger.info(f"Opportunita: {found}")

def main():
    logger.info("BOT FINALE - FootyStats + Bet365")
    
    send_telegram(
        f"🤖 <b>Bot FINALE Online</b>\n\n"
        f"✅ FootyStats: AVG reale\n"
        f"✅ Bet365: Match live\n"
        f"⏱️ Check: <b>{CHECK_INTERVAL}s</b>\n"
        f"📊 AVG > {AVG_THRESHOLD}"
    )
    
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
