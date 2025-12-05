import os
import time
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
import logging
import requests

# =========================
# Logging
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("footystats")

# =========================
# Configuration
# =========================
# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7912248885:AAFwOdg0rX3weVr6NXzW1adcUorvlRY8LyI")
CHAT_ID = os.getenv("CHAT_ID", "6146221712")

# FootyStats API
FOOTYSTATS_API_KEY = os.getenv("FOOTYSTATS_API_KEY", "59c0b4d0f445de0323f7e98880350ed6c583d74907ae64b9b59cfde6a09dd811")

# RapidAPI Soccer-Football-Info
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "785e7ea308mshc88fb29d2de2ac7p12a681jsn71d79500bcd9")
RAPIDAPI_HOST = "soccer-football-info.p.rapidapi.com"

# Settings
AVG_THRESHOLD = float(os.getenv("AVG_THRESHOLD", "2.70"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "180"))  # 3 minuti

# Cache
notified_matches = set()
footystats_cache = {"data": [], "timestamp": 0}
CACHE_TTL = 1800  # 30 minuti

# =========================
# Telegram
# =========================
def send_telegram(msg: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
        if r.ok:
            logger.info("✅ Telegram inviato")
            return True
        logger.error(f"❌ Telegram: {r.status_code}")
        return False
    except Exception as e:
        logger.error(f"❌ Telegram error: {e}")
        return False

# =========================
# FootyStats API
# =========================
def get_footystats_matches():
    global footystats_cache
    
    now = time.time()
    if footystats_cache["data"] and (now - footystats_cache["timestamp"]) < CACHE_TTL:
        logger.info(f"📦 Cache: {len(footystats_cache['data'])} match")
        return footystats_cache["data"]
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = "https://api.footystats.org/v2/matches"
        params = {"key": FOOTYSTATS_API_KEY, "date": today, "include_stats": "true"}
        
        logger.info(f"📥 FootyStats: {today}")
        r = requests.get(url, params=params, timeout=30)
        
        if not r.ok:
            logger.error(f"❌ FootyStats: {r.status_code}")
            return []
        
        data = r.json().get("data", [])
        matches = []
        
        for m in data:
            try:
                stats = m.get("pre_match_stats", {})
                avg = stats.get("avg_goals_per_match_both", 0.0)
                
                if avg == 0.0:
                    ah = stats.get("avg_goals_per_match_home", 0.0)
                    aa = stats.get("avg_goals_per_match_away", 0.0)
                    if ah or aa:
                        avg = (ah + aa) / 2
                
                if avg >= AVG_THRESHOLD:
                    matches.append({
                        "home": m.get("homeTeam", {}).get("name", ""),
                        "away": m.get("awayTeam", {}).get("name", ""),
                        "league": m.get("competition", {}).get("name", ""),
                        "avg": avg
                    })
            except:
                pass
        
        logger.info(f"✅ FootyStats: {len(matches)} match AVG>={AVG_THRESHOLD}")
        footystats_cache = {"data": matches, "timestamp": now}
        return matches
        
    except Exception as e:
        logger.error(f"❌ FootyStats error: {e}")
        return []

# =========================
# RapidAPI Live Matches
# =========================
def get_live_matches():
    try:
        url = f"https://{RAPIDAPI_HOST}/live/full/?l=en_USA&json=on"
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        
        r = requests.get(url, headers=headers, timeout=20)
        
        if not r.ok:
            logger.error(f"❌ RapidAPI: {r.status_code}")
            return []
        
        data = r.json()
        
        # Estrai match live
        live = []
        
        # Struttura tipica: {"result": [{"events": [...]}]}
        if isinstance(data, dict):
            # Cerca eventi nelle possibili chiavi
            events = data.get("result", data.get("events", data.get("data", [])))
            
            if isinstance(events, list) and events:
                # Se il primo elemento ha "events" dentro, estrailo
                if isinstance(events[0], dict) and "events" in events[0]:
                    events = events[0]["events"]
                
                for e in events:
                    try:
                        home = e.get("homeTeam", {}).get("name", e.get("home", ""))
                        away = e.get("awayTeam", {}).get("name", e.get("away", ""))
                        
                        score = e.get("score", {})
                        if isinstance(score, dict):
                            home_score = score.get("home", score.get("current", {}).get("home", 0))
                            away_score = score.get("away", score.get("current", {}).get("away", 0))
                        else:
                            # Fallback: parse stringa tipo "0-0"
                            parts = str(score).split("-")
                            home_score = int(parts[0]) if len(parts) > 0 else 0
                            away_score = int(parts[1]) if len(parts) > 1 else 0
                        
                        status = e.get("status", {})
                        period = status.get("type", status.get("description", ""))
                        
                        live.append({
                            "home": home.strip(),
                            "away": away.strip(),
                            "home_score": home_score,
                            "away_score": away_score,
                            "period": str(period).upper(),
                            "league": e.get("tournament", {}).get("name", e.get("league", ""))
                        })
                    except:
                        pass
        
        logger.info(f"🔴 Live: {len(live)} match")
        return live
        
    except Exception as e:
        logger.error(f"❌ RapidAPI error: {e}")
        return []

# =========================
# Team Matching
# =========================
def normalize(name):
    name = "".join(c for c in unicodedata.normalize("NFKD", name or "") if not unicodedata.combining(c))
    name = re.sub(r"[^a-z0-9]+", " ", name.lower())
    return " ".join(name.split())

def match_teams(fs, live):
    stopwords = {"fc", "cf", "sc", "ac", "club", "cd", "u19", "u20", "u21", "u23", "b", "ii", "iii"}
    
    fs_h = set(t for t in normalize(fs["home"]).split() if t not in stopwords and len(t) >= 3)
    fs_a = set(t for t in normalize(fs["away"]).split() if t not in stopwords and len(t) >= 3)
    live_h = set(t for t in normalize(live["home"]).split() if t not in stopwords and len(t) >= 3)
    live_a = set(t for t in normalize(live["away"]).split() if t not in stopwords and len(t) >= 3)
    
    if (fs_h & live_h) and (fs_a & live_a):
        return True
    
    r_h = SequenceMatcher(None, normalize(fs["home"]), normalize(live["home"])).ratio()
    r_a = SequenceMatcher(None, normalize(fs["away"]), normalize(live["away"])).ratio()
    
    return r_h >= 0.70 and r_a >= 0.70

# =========================
# Logic
# =========================
def is_halftime_00(live):
    """Verifica se è HT con 0-0"""
    period = live.get("period", "")
    
    # Possibili valori: "HT", "HALFTIME", "HALF_TIME", etc.
    if "HT" in period or "HALF" in period:
        return live.get("home_score", 0) == 0 and live.get("away_score", 0) == 0
    
    return False

def check_matches():
    logger.info("=" * 50)
    logger.info("🔍 CHECK")
    
    fs = get_footystats_matches()
    if not fs:
        logger.info("ℹ️ Nessun match FootyStats")
        return
    
    live = get_live_matches()
    if not live:
        logger.info("ℹ️ Nessun live")
        return
    
    found = 0
    
    for f in fs:
        for l in live:
            if not match_teams(f, l):
                continue
            
            if not is_halftime_00(l):
                continue
            
            key = f"{l['home']}|{l['away']}"
            if key in notified_matches:
                continue
            
            msg = (
                "🚨 <b>SEGNALE OVER 1.5 FT</b>\n\n"
                f"⚽ <b>{l['home']} vs {l['away']}</b>\n"
                f"🏆 {l['league']}\n"
                f"📊 AVG: <b>{f['avg']:.2f}</b>\n"
                f"⏱️ <b>INTERVALLO</b> | 1T: <b>0-0</b>\n\n"
                "🎯 <b>PUNTA ORA: OVER 1.5 FT</b>\n"
                "💡 Quote migliori all'HT!"
            )
            
            if send_telegram(msg):
                notified_matches.add(key)
                found += 1
                logger.info(f"🎉 Notifica: {key}")
    
    logger.info(f"📊 Opportunità: {found}")
    logger.info("=" * 50)

# =========================
# Main
# =========================
def main():
    logger.info("🤖 BOT AVVIATO")
    logger.info(f"⚙️ AVG >= {AVG_THRESHOLD} | Check: {CHECK_INTERVAL}s")
    
    send_telegram(
        f"🤖 <b>Bot Online</b>\n\n"
        f"📊 AVG: <b>{AVG_THRESHOLD}</b>\n"
        f"⏱️ Check: <b>{CHECK_INTERVAL}s</b>\n"
        "✅ Monitoraggio HT 0-0 attivo"
    )
    
    while True:
        try:
            check_matches()
            logger.info(f"💤 Sleep {CHECK_INTERVAL}s")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            send_telegram("⛔ Bot arrestato")
            break
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
