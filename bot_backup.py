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
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7912248885:AAFwOdg0rX3weVr6NXzW1adcUorvlRY8LyI')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '6146221712')

ODDS_THRESHOLD = 1.60
CHECK_INTERVAL = 900

def normalize_team_name(name):
    import unicodedata, re
    if not name: return ""
    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    name = re.sub(r'[^a-z0-9\s]', '', name.lower())
    return ' '.join(name.split())

def get_todays_matches():
    """Prendi match con Odds Over 2.5 basse (TUTTE le leghe!)"""
    try:
        url = "https://api.football-data-api.com/todays-matches"
        r = requests.get(url, params={'key': FOOTYSTATS_API_KEY}, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        if not data.get('success'):
            logger.error("❌ API error")
            return []
        
        matches = data.get('data', [])
        logger.info(f"✅ {len(matches)} match oggi (tutte le leghe)")
        
        # Filtra per ODDS
        filtered = []
        for m in matches:
            if m.get('status') not in ['notstarted', '']:
                continue
            
            # CAMPO CORRETTO: odds_ft_over25
            odds_over25 = m.get('odds_ft_over25')
            
            if not odds_over25:
                continue
            
            try:
                odds = float(odds_over25)
                
                # FILTRO: Odds < 1.60 = bookmakers si aspettano tanti gol!
                if odds < ODDS_THRESHOLD:
                    filtered.append({
                        'id': m.get('id'),
                        'home_name': m.get('home_name', 'Unknown'),
                        'away_name': m.get('away_name', 'Unknown'),
                        'home_normalized': normalize_team_name(m.get('home_name')),
                        'away_normalized': normalize_team_name(m.get('away_name')),
                        'odds_over25': round(odds, 2),
                        'competition_name': m.get('competition_name', 'Unknown'),
                        'country': m.get('country', 'Unknown'),
                        'date_unix': m.get('date_unix', 0)
                    })
            except:
                pass
        
        logger.info(f"📊 {len(filtered)} match con Odds Over 2.5 < {ODDS_THRESHOLD}")
        
        # Ordina per odds (più basse = più probabili)
        filtered.sort(key=lambda x: x['odds_over25'])
        
        # Mostra top 15
        if filtered:
            logger.info("\n🔥 TOP 15 MATCH (più probabili):\n")
            for m in filtered[:15]:
                logger.info(f"⚽ {m['home_name']} vs {m['away_name']}")
                logger.info(f"   🏆 {m['country']} - {m['competition_name']}")
                logger.info(f"   📊 Odds O2.5: {m['odds_over25']}\n")
        
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
    odds = m['odds_over25']
    prob = round((1 / odds) * 100)
    
    return f"""🚨 <b>SEGNALE OVER 1.5 FT</b> 🚨

⚽ <b>{m['home_name']} vs {m['away_name']}</b>
🏆 {m['country']} - {m['competition_name']}

⏱ <b>INTERVALLO ({min}') - 0-0</b>

📊 <b>Odds Over 2.5: {odds}</b>
📈 Probabilità Over 2.5: <b>{prob}%</b>

💡 <b>STRATEGIA: OVER 1.5 FT</b>

🔥 Bookmakers si aspettavano 3+ gol!
✅ Servono solo 2 gol per vincere!
⚡ Probabilità Over 1.5 molto alta!
"""

def main():
    logger.info("="*60)
    logger.info("🤖 BOT BETTING - STRATEGIA ODDS")
    logger.info(f"📊 Filtro: Odds Over 2.5 < {ODDS_THRESHOLD}")
    logger.info(f"⏱ Check ogni {CHECK_INTERVAL//60} min")
    logger.info("="*60)
    
    send_telegram(f"🤖 Bot avviato!\n📊 Filtro: Odds Over 2.5 < {ODDS_THRESHOLD}")
    
    monitored, alerted = [], set()
    todays = get_todays_matches()
    
    if todays:
        monitored = todays
        
        if len(monitored) > 20:
            summary = f"📋 <b>Monitoro {len(monitored)} match (top 20):</b>\n\n"
            for m in monitored[:20]:
                summary += f"• {m['home_name']} vs {m['away_name']}\n"
                summary += f"  🏆 {m['competition_name']}\n"
                summary += f"  📊 Odds: {m['odds_over25']}\n\n"
            summary += f"...e altri {len(monitored)-20} match"
        else:
            summary = f"📋 <b>Monitoro {len(monitored)} match:</b>\n\n"
            for m in monitored:
                summary += f"• {m['home_name']} vs {m['away_name']}\n"
                summary += f"  🏆 {m['competition_name']}\n"
                summary += f"  📊 Odds: {m['odds_over25']}\n\n"
        
        send_telegram(summary)
    else:
        send_telegram(f"⚠️ Nessun match oggi con Odds O2.5 < {ODDS_THRESHOLD}")
    
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
                logger.info("🔄 Refresh lista...")
                todays = get_todays_matches()
                if todays:
                    existing = {m['id'] for m in monitored}
                    new_matches = [m for m in todays if m['id'] not in existing]
                    if new_matches:
                        monitored.extend(new_matches)
                        logger.info(f"➕ Aggiunti {len(new_matches)} nuovi match")
            
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
