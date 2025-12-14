import os
import time
import requests
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Credenziali
FOOTYSTATS_API_KEY = os.getenv('FOOTYSTATS_API_KEY', '59c0b4d0f445de0323f7e98880350ed6c583d74907ae64b9b59cfde6a09dd811')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '785e7ea308mshc88fb29d2de2ac7p12a681jsn71d79500bcd9')
RAPIDAPI_HOST = 'soccer-football-info.p.rapidapi.com'
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7969912548:AAFoQzl79K3TiQVnR39ackzVk4JCkDJ3LZQ')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '6146221712')

AVG_THRESHOLD = 2.70
CHECK_INTERVAL = 900

def normalize_team_name(name):
    import unicodedata, re
    if not name: return ""
    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    name = re.sub(r'[^a-z0-9\s]', '', name.lower())
    return ' '.join(name.split())

def get_todays_matches():
    """Prendi match di oggi CON calcolo AVG da PPG (senza chiamate extra!)"""
    try:
        url = "https://api.football-data-api.com/todays-matches"
        r = requests.get(url, params={'key': FOOTYSTATS_API_KEY}, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        if not data.get('success'):
            logger.error("❌ API error")
            return []
        
        matches = data.get('data', [])
        logger.info(f"✅ {len(matches)} match oggi")
        
        # Filtra e calcola AVG direttamente
        filtered = []
        for m in matches:
            if m.get('status') not in ['notstarted', '']:
                continue
            
            # CALCOLO AVG DA PPG (già nella risposta!)
            home_ppg = float(m.get('pre_match_teamA_overall_ppg', 0))
            away_ppg = float(m.get('pre_match_teamB_overall_ppg', 0))
            
            # AVG stimato = media PPG
            avg_estimated = (home_ppg + away_ppg) / 2 if (home_ppg + away_ppg) > 0 else 0
            
            # Se non c'è PPG, usa seasonAVG
            if avg_estimated == 0:
                home_avg = float(m.get('seasonAVG_overall_home', 0))
                away_avg = float(m.get('seasonAVG_overall_away', 0))
                avg_estimated = (home_avg + away_avg) / 2
            
            if avg_estimated >= AVG_THRESHOLD:
                filtered.append({
                    'id': m.get('id'),
                    'home_name': m.get('home_name', 'Unknown'),
                    'away_name': m.get('away_name', 'Unknown'),
                    'home_normalized': normalize_team_name(m.get('home_name')),
                    'away_normalized': normalize_team_name(m.get('away_name')),
                    'avg_potential': round(avg_estimated, 2),
                    'competition_name': m.get('competition_name', 'Unknown'),
                    'date_unix': m.get('date_unix', 0)
                })
        
        logger.info(f"📊 {len(filtered)} match AVG >= {AVG_THRESHOLD}")
        
        # Ordina per AVG
        filtered.sort(key=lambda x: x['avg_potential'], reverse=True)
        
        # Mostra top 10
        for m in filtered[:10]:
            logger.info(f"✅ {m['home_name']} vs {m['away_name']} - AVG: {m['avg_potential']}")
        
        return filtered
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
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
        logger.info(f"⚽ {len(live)} live")
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
    return f"""🚨 <b>SEGNALE OVER 1.5 FT</b>

⚽ <b>{m['home_name']} vs {m['away_name']}</b>
🏆 {m['competition_name']}
📊 <b>AVG: {m['avg_potential']:.2f}</b>

⏱ <b>INTERVALLO ({min}') - 0-0</b>

💡 <b>PUNTA: OVER 1.5 FT</b>
📈 Quote migliori all'HT!"""

def main():
    logger.info("="*60)
    logger.info("🤖 BOT BETTING AVVIATO (OTTIMIZZATO)")
    logger.info(f"📊 AVG >= {AVG_THRESHOLD} | ⏱ Check ogni {CHECK_INTERVAL//60} min")
    logger.info("="*60)
    
    send_telegram("🤖 Bot avviato! (versione ottimizzata)")
    
    monitored, alerted = [], set()
    todays = get_todays_matches()
    
    if todays:
        monitored = todays
        if len(monitored) > 20:
            summary = f"📋 <b>Monitoro {len(monitored)} match (top 20):</b>\n\n"
            for m in monitored[:20]:
                summary += f"• {m['home_name']} vs {m['away_name']} (AVG: {m['avg_potential']:.2f})\n"
            summary += f"\n...e altri {len(monitored)-20} match"
        else:
            summary = f"📋 <b>Monitoro {len(monitored)} match:</b>\n\n"
            for m in monitored:
                summary += f"• {m['home_name']} vs {m['away_name']} (AVG: {m['avg_potential']:.2f})\n"
        send_telegram(summary)
    else:
        send_telegram("⚠️ Nessun match oggi con AVG >= 2.70")
    
    while True:
        try:
            logger.info(f"\n{'='*60}\n🔄 CHECK ({datetime.now().strftime('%H:%M:%S')})\n{'='*60}")
            
            if monitored:
                live = get_live_matches()
                if live:
                    for alert in check_halftime_00(monitored, live):
                        if alert['match']['id'] not in alerted:
                            send_telegram(format_alert(alert))
                            alerted.add(alert['match']['id'])
            
            if datetime.now().minute == 0:
                logger.info("🔄 Refresh...")
                todays = get_todays_matches()
                if todays:
                    existing = {m['id'] for m in monitored}
                    monitored.extend([m for m in todays if m['id'] not in existing])
            
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
