# ⚽ FootyStats Bot - Over 1.5 FT

Bot automatico che identifica opportunità **Over 1.5 FT** su match con alto AVG gol che finiscono 0-0 al primo tempo.

## 🎯 Strategia

```
FootyStats API → Match AVG > 2.70
       ↓
Live API → Controllo match in corso
       ↓
HT 0-0 → Notifica Telegram
       ↓
🎯 SCOMMESSA: Over 1.5 FT
```

## 🚀 Deploy su Render

### 1. Fork/Clone questo repo

### 2. Vai su [Render](https://render.com)

### 3. Crea nuovo **Background Worker**

### 4. Configura:
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python bot.py`

### 5. Aggiungi Environment Variables:
```
TELEGRAM_TOKEN=7912248885:AAFwOdg0rX3weVr6NXzW1adcUorvlRY8LyI
CHAT_ID=6146221712
FOOTYSTATS_API_KEY=59c0b4d0f445de0323f7e98880350ed6c583d74907ae64b9b59cfde6a09dd811
RAPIDAPI_KEY=785e7ea308mshc88fb29d2de2ac7p12a681jsn71d79500bcd9
AVG_THRESHOLD=2.70
CHECK_INTERVAL=180
```

### 6. Deploy! 🎉

## 📊 Features

- ✅ FootyStats API (match con statistiche)
- ✅ RapidAPI Live (match in corso real-time)
- ✅ Rilevamento automatico HT 0-0
- ✅ Notifiche Telegram instant
- ✅ Cache intelligente (30 min)
- ✅ Matching robusto nomi squadre

## ⚙️ Configurazione

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `AVG_THRESHOLD` | 2.70 | Soglia minima AVG gol |
| `CHECK_INTERVAL` | 180 | Secondi tra controlli |

## 📱 Esempio Notifica

```
🚨 SEGNALE OVER 1.5 FT

⚽ Real Madrid vs Barcelona
🏆 La Liga
📊 AVG: 3.45
⏱️ INTERVALLO | 1T: 0-0

🎯 PUNTA ORA: OVER 1.5 FT
💡 Quote migliori all'HT!
```

## ⚠️ Disclaimer

Bot educativo. Le scommesse comportano rischi. Usa responsabilmente.

---

**Created with ❤️ | December 2024**
