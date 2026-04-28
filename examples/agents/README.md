# ATLAS Beispiel-Agenten

Diese Agenten sind **Referenz-Implementierungen** für die Domäne PLM-Koordination im Schiffbau.
Sie sind **nicht automatisch aktiv** — der Schwarm startet leer.

## Wie aktivieren

### Option A: Einzelnen Agenten manuell hinzufügen
```bash
atlas spawn "plm_coordinator" \
  --desc "PLM-Koordination für CATIA, ENOVIA, SAP und P&ID im Schiffbau" \
  --skills "CATIA V6,ENOVIA,SAP,P&ID,Prozessanalyse"
```

### Option B: Ganzes Team für eine Domäne generieren
```bash
atlas init "PLM Business Coordination im Schiffbau"
```
Der Swarm-Architekt erstellt dann ein maßgeschneidertes Team.

### Option C: Agent-Dateien direkt kopieren
```bash
cp -r examples/agents/plm_coordinator atlas_agents/
# dann in atlas_memory/global/agent_registry.json manuell eintragen
```

## Enthaltene Beispiel-Agenten

| Agent | Domäne | Beschreibung |
|-------|--------|--------------|
| `plm_coordinator` | PLM/Schiffbau | Zentrale PLM-Koordination, CATIA, ENOVIA, SAP |
| `sr_writer` | PLM/Schiffbau | Service Requests und Bug Reports |
| `automation_engineer` | PLM/Schiffbau | Python, Power Automate, VBA Automatisierung |
| `demand_writer` | PLM/Schiffbau | IT Demands, Business Cases, ROI |
| `daily_briefing` | PLM/Schiffbau | Tagesplanung und Priorisierung |
