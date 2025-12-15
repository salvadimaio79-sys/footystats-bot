import os
import time
import csv
import re
import unicodedata
from io import StringIO
from datetime import datetime, timezone
from difflib import SequenceMatcher

import logging
import requests

# =========================
# Logging
# =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("footystats-bot")

# =========================
# Environment
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN", "7912248885:AAFwOdg0rX3weVr6NXzW1adcUorvlRY8LyI")
CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID", "6146221712")

RAPIDAPI_KEY   = os.getenv("RAPIDAPI_KEY", "785e7ea308mshc88fb29d2de2ac7p12a681jsn71d79500bcd9")
RAPIDAPI_HOST  = "soccer-football-info.p.rapidapi.com"

# CSV su GitHub
GITHUB_CSV_URL = "https://raw.githubusercontent.com/salvadimaio79-sys/footystats-bot/main/matches_today.csv"

# Filtri
AVG_GOALS_THRESHOLD = float(os.getenv("AVG_GOALS_THRESHOLD", "2.70"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "180"))  # 3 minuti

# Esclusioni leghe
LEAGUE_EXCLUDE_KEYWORDS = [
    "esoccer", "volta", "8 mins", "h2h", "e-football", "fifa", "pes"
]

# Cache notifiche
notified_matches: set[str] = set()

# =========================
# Telegram
# =========================
def send_telegram_message(message: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logger.error("TELEGRAM_TOKEN/CHAT_ID mancanti")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=15)
        if r.ok:
            logger.info("✅ Telegram inviato")
            return True
        logger.error("❌ Telegram %s: %s", r.status_code, r.text)
    except Exception as e:
        logger.exception("❌ Telegram exception: %s", e)
    return False

# =========================
# CSV da GitHub
# =========================
def load_csv_from_github():
    try:
        logger.info("📥 Scarico CSV: %s", GITHUB_CSV_URL)
        r = requests.get(GITHUB_CSV_URL, timeout=30)
        r.raise_for_status()
        rows = list(csv.DictReader(StringIO(r.text)))
        logger.info("✅ CSV caricato (%d righe)", len(rows))
        return rows
    except Exception as e:
        logger.exception("❌ Errore caricamento CSV: %s", e)
        return []

def get_avg_goals(row) -> float:
    """Estrae AVG Goals dal CSV"""
    keys = [
        "Average Goals", "AVG Goals", "AvgGoals", "Avg Goals",
        "Avg Total Goals", "Average Total Goals"
    ]
    for k in keys:
        v = row.get(k)
        if v and str(v).strip():
            try:
                return float(str(v).replace(",", "."))
            except:
                pass
    return 0.0

def filter_matches_by_avg(matches):
    """Filtra match con AVG >= soglia ED esclude esports"""
    filtered = []
    excluded_esports = 0
    
    for m in matches:
        try:
            # Escludi esports/virtuali
            league = m.get("League", "").lower()
            country = m.get("Country", "").lower()
            
            # Lista esclusioni
            exclude_keywords = [
                "esoccer", "esports", "e-soccer", "e-sports",
                "fifa", "pes", "efootball", "e-football",
                "volta", "8 mins", "h2h", "battle",
                "virtual", "cyber"
            ]
            
            # Se contiene keyword esclusa, salta
            if any(kw in league or kw in country for kw in exclude_keywords):
                excluded_esports += 1
                continue
            
            # Controlla AVG
            avg = get_avg_goals(m)
            if avg >= AVG_GOALS_THRESHOLD:
                filtered.append(m)
        except:
            pass
    
    logger.info("📊 Filtrati %d match con AVG >= %.2f", len(filtered), AVG_GOALS_THRESHOLD)
    logger.info("❌ Esclusi %d match esports/virtuali", excluded_esports)
    
    # Mostra top 10
    if filtered:
        sorted_matches = sorted(filtered, key=lambda x: get_avg_goals(x), reverse=True)
        logger.info("\n🔥 TOP 10 MATCH:\n")
        for m in sorted_matches[:10]:
            home = m.get("Home Team", "")
            away = m.get("Away Team", "")
            avg = get_avg_goals(m)
            league = m.get("League", "")
            logger.info(f"⚽ {home} vs {away} | AVG: {avg:.2f} | {league}")
    
    return filtered

# =========================
# Live events (Soccer Football Info API)
# =========================
def get_live_matches():
    """Prendi match live da Soccer Football Info API"""
    try:
        url = f"https://{RAPIDAPI_HOST}/live/full/"
        headers = {
            'x-rapidapi-key': RAPIDAPI_KEY,
            'x-rapidapi-host': RAPIDAPI_HOST
        }
        params = {
            'i': 'en_US',
            'f': 'json',
            'e': 'no'
        }
        
        r = requests.get(url, headers=headers, params=params, timeout=25)
        
        if not r.ok:
            logger.error("❌ API live: HTTP %s", r.status_code)
            return []
        
        data = r.json()
        events = data.get("result", [])
        
        # Filtra ed estrai dati
        live_matches = []
        for event in events:
            team_a = event.get("teamA", {})
            team_b = event.get("teamB", {})
            
            home_name = team_a.get("name", "").strip()
            away_name = team_b.get("name", "").strip()
            
            if not home_name or not away_name:
                continue
            
            # Estrai lega
            league = event.get("league", {})
            league_name = league.get("name", "Unknown") if isinstance(league, dict) else str(league)
            
            # Escludi esports/virtuals
            if any(kw in league_name.lower() for kw in LEAGUE_EXCLUDE_KEYWORDS):
                continue
            
            # Estrai minuto
            timer = event.get("timer", "")
            minute = 0
            if timer and ':' in timer:
                try:
                    minute = int(timer.split(':')[0])
                except:
                    minute = 0
            
            # Estrai score
            score_a = team_a.get("score", {})
            score_b = team_b.get("score", {})
            home_score = int(score_a.get("f", 0)) if isinstance(score_a, dict) else 0
            away_score = int(score_b.get("f", 0)) if isinstance(score_b, dict) else 0
            
            live_matches.append({
                "home": home_name,
                "away": away_name,
                "league": league_name,
                "minute": minute,
                "home_score": home_score,
                "away_score": away_score,
                "score_str": f"{home_score}-{away_score}"
            })
        
        logger.info("⚽ %d match live (dopo filtri)", len(live_matches))
        return live_matches
        
    except Exception as e:
        logger.exception("❌ Errore get_live_matches: %s", e)
        return []

# =========================
# Matching nomi squadre (TUA LOGICA ORIGINALE)
# =========================
STOPWORDS = {
    "fc", "cf", "sc", "ac", "club", "cd", "de", "del", "da", "do", "d",
    "u19", "u20", "u21", "u23", "b", "ii", "iii", "women", "w",
    "reserves", "team", "sv", "afc", "youth", "if", "fk"
}

def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s or "")
        if not unicodedata.combining(c)
    )

def norm_text(s: str) -> str:
    s = strip_accents(s).lower()
    s = re.sub(r"\(.*?\)", " ", s)  # rimuovi parentesi
    s = re.sub(r"[''`]", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())

def team_tokens(name: str) -> set[str]:
    toks = [t for t in norm_text(name).split() if t and t not in STOPWORDS]
    toks = [t for t in toks if len(t) >= 3 or t.isdigit()]
    return set(toks)

def token_match(a: str, b: str) -> bool:
    A, B = team_tokens(a), team_tokens(b)
    if not A or not B:
        return False
    if A == B or A.issubset(B) or B.issubset(A):
        return True
    inter = A & B
    if len(A) == 1 or len(B) == 1:
        return len(inter) >= 1
    return len(inter) >= 2

def fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_text(a), norm_text(b)).ratio()

def match_teams(csv_match, live_match) -> bool:
    """Verifica se CSV match e live match sono lo stesso"""
    csv_home = csv_match.get("Home Team") or csv_match.get("Home") or ""
    csv_away = csv_match.get("Away Team") or csv_match.get("Away") or ""
    live_home = live_match.get("home", "")
    live_away = live_match.get("away", "")
    
    # 1) Token match (veloce)
    if token_match(csv_home, live_home) and token_match(csv_away, live_away):
        return True
    
    # 2) Check acronimi (es. "ABB" vs "Academia Balompie Boliviano")
    if is_acronym_match(csv_home, live_home) and is_acronym_match(csv_away, live_away):
        return True
    
    # 3) Fuzzy fallback
    rh = fuzzy_ratio(csv_home, live_home)
    ra = fuzzy_ratio(csv_away, live_away)
    if (rh >= 0.72 and ra >= 0.60) or (rh >= 0.60 and ra >= 0.72):
        return True
    
    return False

def is_acronym_match(short: str, long: str) -> bool:
    """Check se short è acronimo di long (es. ABB = Academia Balompie Boliviano)"""
    short_clean = norm_text(short).replace(" ", "")
    long_words = norm_text(long).split()
    
    # Filtra stopwords per acronimo
    long_words_filtered = [w for w in long_words if w not in STOPWORDS and len(w) >= 3]
    
    # Se short non è corto, non è un acronimo
    if len(short_clean) < 2 or len(short_clean) > 6:
        return token_match(short, long)
    
    # Prova a costruire acronimo da long (senza stopwords)
    if len(long_words_filtered) >= len(short_clean):
        acronym = "".join(w[0] for w in long_words_filtered if w)
        # Match se acronimo corrisponde
        if short_clean == acronym[:len(short_clean)]:
            return True
        if short_clean == acronym:
            return True
    
    # Se non è acronimo, usa token match normale
    return token_match(short, long)

# =========================
# Business Logic
# =========================
def check_matches():
    logger.info("\n" + "=" * 70)
    logger.info("🔄 INIZIO CONTROLLO (%s)", datetime.now().strftime("%H:%M:%S"))
    logger.info("=" * 70)
    
    # Carica CSV
    csv_matches = load_csv_from_github()
    if not csv_matches:
        logger.warning("⚠️ CSV vuoto o non caricato")
        return
    
    # Filtra per AVG
    filtered = filter_matches_by_avg(csv_matches)
    if not filtered:
        logger.info("⚠️ Nessun match con AVG >= %.2f", AVG_GOALS_THRESHOLD)
        return
    
    # Prendi live
    live = get_live_matches()
    if not live:
        logger.info("⚠️ Nessun match live al momento")
        return
    
    # Cerca opportunità
    matched = 0
    opportunities = 0
    
    logger.info("\n🔍 Cerco abbinamenti CSV ↔ Live...")
    
    # DEBUG: Mostra i match live
    logger.info("\n📋 MATCH LIVE TROVATI:")
    for lm in live[:10]:  # Mostra primi 10
        logger.info("  • %s vs %s (%d') - %s", 
                   lm['home'], lm['away'], lm['minute'], lm['league'])
    
    # DEBUG: Controlla se "Aurora" è nel CSV
    logger.info("\n🔎 Cerco 'Aurora' nel CSV...")
    aurora_found = False
    for csv_m in filtered:
        home = csv_m.get("Home Team", "").lower()
        away = csv_m.get("Away Team", "").lower()
        if "aurora" in home or "aurora" in away:
            logger.info("  ✅ TROVATO nel CSV: %s vs %s", 
                       csv_m.get("Home Team"), csv_m.get("Away Team"))
            aurora_found = True
    
    if not aurora_found:
        logger.info("  ❌ Aurora NON trovato nel CSV!")
    
    for csv_m in filtered:
        csv_home = csv_m.get("Home Team", "")
        csv_away = csv_m.get("Away Team", "")
        
        # DEBUG: Mostra primi 5 match CSV che cerca
        if matched == 0 and filtered.index(csv_m) < 5:
            logger.info("\n🔎 Cerco nel CSV: %s vs %s", csv_home, csv_away)
        
        for live_m in live:
            # Match squadre
            if not match_teams(csv_m, live_m):
                continue
            
            matched += 1
            minute = live_m.get("minute", 0)
            home_score = live_m.get("home_score", 0)
            away_score = live_m.get("away_score", 0)
            
            # Log match trovato
            logger.info("✅ ABBINATO: %s vs %s | %d' | %s | CSV: %s vs %s", 
                       live_m['home'], live_m['away'], minute, live_m['score_str'],
                       csv_home, csv_away)
            
            # CONDIZIONE: Match a HALFTIME (44-47') E risultato 0-0
            # Invia notifica SUBITO quando trova queste condizioni!
            if 44 <= minute <= 47 and home_score == 0 and away_score == 0:
                # Genera chiave unica per evitare notifiche duplicate
                key = f"{live_m['home']}|{live_m['away']}"
                
                # Se già notificato questo match, salta
                if key in notified_matches:
                    continue
                
                # Prepara messaggio alert
                avg = get_avg_goals(csv_m)
                
                msg = (
                    "🚨 <b>SEGNALE OVER 1.5 FT!</b> 🚨\n\n"
                    f"⚽ <b>{live_m['home']} vs {live_m['away']}</b>\n"
                    f"🏆 {live_m['league']}\n\n"
                    f"⏱️ <b>MINUTO: {minute}'</b>\n"
                    f"📊 <b>RISULTATO: {live_m['score_str']}</b>\n\n"
                    f"📈 AVG Goals: <b>{avg:.2f}</b>\n\n"
                    "💡 <b>STRATEGIA: PUNTA OVER 1.5 FT</b>\n"
                    "✅ Match 0-0 a fine primo tempo!\n"
                    "🔥 Squadre ad alto punteggio!"
                )
                
                # Invia
                if send_telegram_message(msg):
                    notified_matches.add(key)
                    opportunities += 1
                    logger.info("🎯 ALERT INVIATO: %s vs %s (%d')", 
                              live_m['home'], live_m['away'], minute)
    
    logger.info("📊 Riepilogo: %d abbinati CSV↔Live | %d opportunità trovate", 
                matched, opportunities)
    logger.info("=" * 70)

def main():
    logger.info("\n" + "=" * 70)
    logger.info("🤖 FOOTYSTATS BOT - VERSIONE FINALE")
    logger.info("=" * 70)
    logger.info(f"📊 Soglia AVG: {AVG_GOALS_THRESHOLD}")
    logger.info(f"⏱️ Check ogni: {CHECK_INTERVAL} secondi ({CHECK_INTERVAL//60} minuti)")
    logger.info(f"📥 CSV: {GITHUB_CSV_URL}")
    logger.info("=" * 70)
    
    # Messaggio startup
    send_telegram_message(
        "🤖 <b>Bot FootyStats Avviato!</b>\n\n"
        f"📊 Soglia AVG: {AVG_GOALS_THRESHOLD}\n"
        f"⏱️ Check ogni {CHECK_INTERVAL//60} minuti\n"
        "✅ Monitoraggio attivo..."
    )
    
    while True:
        try:
            check_matches()
            logger.info("⏳ Sleep %d secondi...\n", CHECK_INTERVAL)
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("\n👋 Bot fermato dall'utente")
            send_telegram_message("🛑 Bot arrestato")
            break
            
        except Exception as e:
            logger.exception("❌ Errore nel loop principale: %s", e)
            time.sleep(60)

if __name__ == "__main__":
    main()
