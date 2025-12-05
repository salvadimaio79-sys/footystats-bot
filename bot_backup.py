import requests
from datetime import datetime

API_KEY = "59c0b4d0f445de0323f7e98880350ed6c583d74907ae64b9b59cfde6a09dd811"

print("TEST FOOTYSTATS")
print("=" * 60)

url = "https://api.football-data-api.com/todays-matches"
params = {"key": API_KEY}

print(f"URL: {url}")
print(f"Data: {datetime.now().strftime('%Y-%m-%d')}")
print()

try:
    r = requests.get(url, params=params, timeout=30)
    print(f"Status: {r.status_code}")
    
    if r.status_code == 429:
        print("RATE LIMIT!")
        exit()
    
    if not r.ok:
        print(f"Errore: {r.text[:500]}")
        exit()
    
    data = r.json()
    matches = data.get("data", [])
    
    print(f"Match totali: {len(matches)}")
    
    if len(matches) == 0:
        print("Nessun match oggi")
        exit()
    
    # Conta match con AVG >= 2.5
    count = 0
    for m in matches:
        stats = m.get("stats", {})
        avg = float(stats.get("avg_goals_per_match_both", 0))
        
        if avg == 0:
            avg_h = float(stats.get("avg_goals_per_match_home", 0))
            avg_a = float(stats.get("avg_goals_per_match_away", 0))
            if avg_h > 0 and avg_a > 0:
                avg = (avg_h + avg_a) / 2
        
        if avg >= 2.5:
            count += 1
            home = m.get("home_name", "")
            away = m.get("away_name", "")
            print(f"\n{count}. {home} vs {away} | AVG: {avg:.2f}")
    
    print(f"\n{'='*60}")
    print(f"TOTALE AVG >= 2.5: {count}/{len(matches)}")

except Exception as e:
    print(f"ERRORE: {e}")
