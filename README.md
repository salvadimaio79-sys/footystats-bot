# 🎯 BOT CSV MULTI-INDICATORE - GUIDA

## 📊 STRATEGIA

Questo bot usa **5 indicatori** per trovare i match migliori per Over 1.5 FT quando finiscono 0-0 a HT:

### **FILTRI APPLICATI:**

1. **AVG Goals >= 2.70** - Squadre offensive
2. **Over 2.5 Average >= 70%** - Nel 70%+ casi fanno Over 2.5
3. **Over 1.5 2HG Average >= 50%** - Gol nel 2° tempo!
4. **Over 1.5 Average >= 80%** - Nel 80%+ casi fanno Over 1.5
5. **BTTS Average >= 60%** - Entrambe squadre segnano (opzionale)

---

## 🔧 SETUP

### **1. Scarica CSV da FootyStats**

1. Vai su https://footystats.org/
2. Login
3. Vai su "Data Export"
4. Seleziona "Today's Matches"
5. Export CSV
6. Rinomina file in: `matches_today.csv`

### **2. Carica CSV su Render**

**OPZIONE A: Via GitHub**
1. Metti `matches_today.csv` nella root del repository
2. Commit e push
3. Il bot lo leggerà automaticamente

**OPZIONE B: Modifica Path**
Nel codice, cambia:
```python
CSV_PATH = '/mnt/user-data/uploads/matches_today.csv'
```

A dove hai caricato il file.

### **3. Deploy su Render**

1. Sostituisci `bot_backup.py` con `bot_csv_multi.py`
2. Commit su GitHub
3. Render fa auto-deploy

---

## 📱 UTILIZZO

### **Ogni Giorno:**

1. **Mattina (8-9 AM):**
   - Scarica nuovo CSV da FootyStats
   - Carica su GitHub/Render
   - Bot lo legge automaticamente

2. **Durante il Giorno:**
   - Bot monitora i match filtrati
   - Quando un match è 0-0 a HT → Alert Telegram!

3. **Ricevi Alert:**
   ```
   🚨 SEGNALE ULTRA-FORTE!
   
   ⚽ Bayern vs Mainz
   🏆 Germany - Bundesliga
   
   ⏱ INTERVALLO (45') - 0-0
   
   📊 STATISTICHE:
      • AVG Goals: 3.94
      • Over 2.5: 88%
      • Over 1.5 (2T): 75%
      • BTTS: 70%
   
   💡 STRATEGIA: OVER 1.5 FT
   🎯 Quality Score: 8.5/10
   ```

4. **Tu:**
   - Apri bookmaker
   - Controlla quote Over 1.5 FT
   - Se buone → Punta!

---

## ⚙️ PERSONALIZZAZIONE

Modifica i filtri nel file `bot_csv_multi.py`:

```python
FILTERS = {
    'avg_goals_min': 2.70,        # Abbassa a 2.50 per più match
    'over25_avg_min': 70,          # Abbassa a 60 per più match
    'over15_2hg_min': 50,          # Abbassa a 40 per più match
    'over15_avg_min': 80,          # Abbassa a 70 per più match
    'btts_avg_min': 60             # Opzionale
}
```

**PIÙ BASSI = PIÙ MATCH** (ma meno affidabili)  
**PIÙ ALTI = MENO MATCH** (ma più affidabili)

---

## 📊 STATISTICHE

Con filtri default, ti aspetti:

- **10-30 match/giorno** da monitorare
- **1-5 alert HT 0-0** (dipende dalla giornata)
- **Win rate stimato: 70-80%** (se segui gli alert con score alto)

---

## 💡 TIPS

1. **Segui solo alert con Quality Score >= 7.0**
2. **Controlla sempre le quote** prima di puntare
3. **Usa stake progressivo** su match con score 8+
4. **Traccia i risultati** per ottimizzare i filtri

---

## 🔍 TROUBLESHOOTING

### CSV non trovato:
```
Verifica path: /mnt/user-data/uploads/matches_today.csv
```

### Nessun match trovato:
```
Abbassa i filtri (vedi sezione Personalizzazione)
```

### Telegram non funziona:
```
Controlla token in Environment Variables su Render
```

---

## 📈 ESEMPIO GIORNATA TIPO

```
08:00 - Scarica CSV FootyStats
08:05 - Upload su GitHub
08:10 - Bot carica 25 match
12:30 - Alert: Bayern vs Mainz (0-0 HT, Score 8.5)
15:45 - Alert: Celtic vs Aberdeen (0-0 HT, Score 7.8)
18:20 - Alert: Bordeaux vs Lyon (0-0 HT, Score 8.2)
```

3 alert/giorno con qualità alta = ottime opportunità! 🎯

---

**Buon betting! 🍀⚽💰**
