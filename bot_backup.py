import os
import csv
import time
import requests
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Credenziali
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '785e7ea308mshc88fb29d2de2ac7p12a681jsn71d79500bcd9')
RAPIDAPI_HOST = 'soccer-football-info.p.rapidapi.com'
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7912248885:AAFwOdg0rX3weVr6NXzW1adcUorvlRY8LyI')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '6146221712')

# Path CSV (caricato manualmente)
CSV_PATH = '/mnt/user-data/uploads/matches_today.csv'

CHECK_INTERVAL = 900  # 15 minuti

# ============================================
# FILTRI MULTI-INDICATORE
# ============================================

FILTERS = {
    'avg_goals_min': 2.70,        # AVG Goals minimo
    'over25_avg_min': 70,          # Over 2.5 % minimo
    'over15_2hg_min': 50,          # Over 1.5 nel 2° tempo % minimo
    'over15_avg_min': 80,          # Over 1.5 generale % minimo
    'btts_avg_min': 60             # BTTS % minimo (opzionale)
}

def normalize_team_name(name):
    import unicodedata, re
    if not name: return ""
    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    name = re.sub(r'[^a-z0-9\s]', '', name.lower())
    return ' '.join(name.split())

def load_matches_from_csv():
    """Carica match dal CSV con filtro multi-indicatore"""
    try:
        if not os.path.exists(CSV_PATH):
            logger.error(f"❌ File CSV non trovato: {CSV_PATH}")
            return []
        
        matches = []
        
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                status = row.get('Match Status', '')
                
                # Solo match non iniziati
                if status not in ['incomplete', 'notstarted', '']:
                    continue
                
                try:
                    # Estrai indicatori
                    avg_goals = float(row.get('Average Goals', 0))
                    over15_avg = float(row.get('Over15 Average', 0))
                    over25_avg = float(row.get('Over25 Average', 0))
                    btts_avg = float(row.get('BTTS Average', 0))
                    over15_2hg = float(row.get('Over15 2HG Average', 0))
                    
                    # APPLICA FILTRI
                    if (avg_goals >= FILTERS['avg_goals_min'] and
                        over25_avg >= FILTERS['over25_avg_min'] and
                        over15_2hg >= FILTERS['over15_2hg_min'] and
                        over15_avg >= FILTERS['over15_avg_min']):
                        
                        # Match qualificato!
                        home = row.get('Home Team', 'Unknown')
                        away = row.get('Away Team', 'Unknown')
                        
                        matches.append({
                            'home_name': home,
                            'away_name': away,
                            'home_normalized': normalize_team_name(home),
                            'away_normalized': normalize_team_name(away),
                            'league': row.get('League', 'Unknown'),
                            'country': row.get('Country', 'Unknown'),
                            # Statistiche
                            'avg_goals': round(avg_goals, 2),
                            'over15_avg': round(over15_avg, 1),
                            'over25_avg': round(over25_avg, 1),
                            'btts_avg': round(btts_avg, 1),
                            'over15_2hg': round(over15_2hg, 1),
                            # Score qualità
                            'quality_score': round(avg_goals + over25_avg/100 + over15_2hg/100, 2)
                        })
                
                except Exception as e:
                    continue
        
        # Ordina per quality score
        matches.sort(key=lambda x: x['quality_score'], reverse=True)
        
        logger.info(f"✅ Caricati {len(matches)} match dal CSV")
        
        # Mostra top 10
        if matches:
            logger.info("\n🔥 TOP 10 MATCH:\n")
            for m in matches[:10]:
                logger.info(f"⚽ {m['home_name']} vs {m['away_name']}")
                logger.info(f"   🏆 {m['country']} - {m['league']}")
                logger.info(f"   📊 AVG: {m['avg_goals']} | O2.5: {m['over25_avg']}% | O1.5 2T: {m['over15_2hg']}%\n")
        
        return matches
        
    except Exception as e:
        logger.error(f"❌ Errore lettura CSV: {e}")
        return []

def get_live_matches():
    try:
        url = f"https://{RAPIDAPI_HOST}/live/full/"
        headers = {'x-rapidapi-key': RAPIDAPI_KEY, 'x-rapidapi-host': RAPIDAPI_HOST}
        params = {'i': 'en_US', 'f': 'json', 'e': 'no'}
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        live = data.get('result', [])
        logger.info(f"⚽ {len(live)} match live")
        return live
    except Exception as e:
        logger.error(f"❌ Live: {e}")
        return []

def check_halftime_00(monitored, live):
    alerts = []
    for mon in monitored:
        for l in live:
            team_a, team_b = l.get('teamA', {}), l.get('teamB', {})
            live_home_norm = normalize_team_name(team_a.get('name', ''))
            live_away_norm = normalize_team_name(team_b.get('name', ''))
            
            if (mon['home_normalized'] in live_home_norm or live_home_norm in mon['home_normalized']) and \
               (mon['away_normalized'] in live_away_norm or live_away_norm in mon['away_normalized']):
                
                timer = l.get('timer', '')
                minute = int(timer.split(':')[0]) if timer and ':' in timer else 0
                
                if 44 <= minute <= 47:
                    score_a, score_b = team_a.get('score', {}), team_b.get('score', {})
                    if int(score_a.get('f', 0)) == 0 and int(score_b.get('f', 0)) == 0:
                        alerts.append({'match': mon, 'minute': minute})
                        logger.info(f"🎯 {mon['home_name']} vs {mon['away_name']} 0-0 HT!")
                break
    return alerts

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=10)
        r.raise_for_status()
        logger.info("✅ Telegram OK")
        return True
    except Exception as e:
        logger.error(f"❌ Telegram: {e}")
        return False

def format_alert(alert):
    m, min = alert['match'], alert['minute']
    
    return f"""🚨 <b>SEGNALE ULTRA-FORTE!</b> 🚨

⚽ <b>{m['home_name']} vs {m['away_name']}</b>
🏆 {m['country']} - {m['league']}

⏱ <b>INTERVALLO ({min}') - 0-0</b>

📊 <b>STATISTICHE:</b>
   • AVG Goals: <b>{m['avg_goals']}</b>
   • Over 2.5: <b>{m['over25_avg']}%</b>
   • Over 1.5 (2T): <b>{m['over15_2hg']}%</b>
   • BTTS: <b>{m['btts_avg']}%</b>

💡 <b>STRATEGIA: OVER 1.5 FT</b>

🔥 Match con TUTTI gli indicatori positivi!
✅ Nel 2° tempo segnano in media {m['over15_2hg']}% volte
⚡ Probabilità MOLTO ALTA di 2+ gol FT!

🎯 <b>Quality Score: {m['quality_score']}/10</b>
"""

def main():
    logger.info("="*70)
    logger.info("🤖 BOT BETTING - STRATEGIA MULTI-INDICATORE CSV")
    logger.info("="*70)
    logger.info(f"\n📊 FILTRI ATTIVI:")
    logger.info(f"   • AVG Goals >= {FILTERS['avg_goals_min']}")
    logger.info(f"   • Over 2.5 % >= {FILTERS['over25_avg_min']}%")
    logger.info(f"   • Over 1.5 (2T) % >= {FILTERS['over15_2hg_min']}%")
    logger.info(f"   • Over 1.5 % >= {FILTERS['over15_avg_min']}%")
    logger.info(f"\n⏱ Check ogni {CHECK_INTERVAL//60} minuti")
    logger.info("="*70)
    
    send_telegram("🤖 Bot CSV Multi-Indicatore avviato!\n📊 Carico match dal CSV...")
    
    # Carica match dal CSV
    monitored = load_matches_from_csv()
    alerted = set()
    
    if monitored:
        # Prepara summary
        if len(monitored) > 15:
            summary = f"📋 <b>Monitoro {len(monitored)} match (top 15):</b>\n\n"
            for m in monitored[:15]:
                summary += f"• {m['home_name']} vs {m['away_name']}\n"
                summary += f"  📊 AVG: {m['avg_goals']} | O2.5: {m['over25_avg']}%\n"
                summary += f"  🔥 Score: {m['quality_score']}/10\n\n"
            summary += f"...e altri {len(monitored)-15} match"
        else:
            summary = f"📋 <b>Monitoro {len(monitored)} match:</b>\n\n"
            for m in monitored:
                summary += f"• {m['home_name']} vs {m['away_name']}\n"
                summary += f"  📊 AVG: {m['avg_goals']} | O2.5: {m['over25_avg']}%\n"
                summary += f"  🔥 Score: {m['quality_score']}/10\n\n"
        
        send_telegram(summary)
    else:
        send_telegram("⚠️ Nessun match trovato nel CSV con i filtri attuali.\n\n💡 Carica il CSV in /mnt/user-data/uploads/matches_today.csv")
    
    # Loop monitoring
    while True:
        try:
            logger.info(f"\n{'='*70}\n🔄 CHECK ({datetime.now().strftime('%H:%M:%S')})\n{'='*70}")
            
            if monitored:
                live = get_live_matches()
                if live:
                    for alert in check_halftime_00(monitored, live):
                        match_id = f"{alert['match']['home_name']}_{alert['match']['away_name']}"
                        
                        if match_id not in alerted:
                            send_telegram(format_alert(alert))
                            alerted.add(match_id)
            
            logger.info(f"⏳ Sleep {CHECK_INTERVAL//60} min...")
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            send_telegram("🛑 Bot fermato")
            break
        except Exception as e:
            logger.error(f"❌ {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
