# ATLAS Swarm

**Dezentrales Schwarm-AIOS für PLM-Koordination und technische Arbeitsorganisation im Schiffbau.**

Inspiriert vom Blackboard-Prinzip und Stigmergy-Konzept aus der Schwarmintelligenz-Forschung.
Jeder Agent ist ein autonomer Hermes-Agent mit privatem Wissen und Zugang zum globalen Pool.

---

## Architektur

```
User Input
    ↓
Swarm Dispatcher (Router)
    ↓
Autonomer Hermes-Agent
    ├── Privater Stack: system.md · memory.md · examples.md · skills.md
    └── Globaler Pool:  atlas_knowledge.md · learnings.jsonl · skill_index.json
    ↓
Output + Auto-Lernen → memory.md + learnings.jsonl
    ↓
Blackboard-Signal (andere Agenten können reagieren)
```

### Kern-Mechanismen

| Mechanismus | Beschreibung |
|---|---|
| **Blackboard** | Geteilter Wissensspeicher — Agenten pinnen Signale, andere reagieren autonom |
| **Stigmergy** | Agenten hinterlassen "Pheromone" (Signale) bei Lücken oder Erkenntnissen |
| **Auto-Lernen** | Nach jedem Lauf destilliert das LLM eine Regel → private memory.md + globaler Pool |
| **Async Delegation** | Agenten delegieren Subtasks asynchron — Ergebnisse beim nächsten Lauf |
| **Agent Spawn** | Dispatcher erkennt unbekannte Tasks → neuer Agent wird generiert (mit Bestätigung) |

---

## Installation

```bash
git clone https://github.com/DEIN_USER/atlas-swarm
cd atlas-swarm
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env  # OPENROUTER_API_KEY eintragen

# Globales Kommando (optional)
chmod +x atlas.sh
ln -sf $(pwd)/atlas.sh /usr/local/bin/atlas
```

---

## Verwendung

```bash
# Auto-Routing (Dispatcher wählt Agent)
python -m atlas_run.atlas run "Pfeile in P&IDs werden falsch gedruckt"

# Gezielter Agent
python -m atlas_run.atlas run "SR erstellen" --agent sr_writer

# Schwarm-Status
python -m atlas_run.atlas status

# Globalen Lernpool anzeigen
python -m atlas_run.atlas learn

# Neuen Agenten spawnen (mit Bestätigung)
python -m atlas_run.atlas spawn "quality_checker" --desc "QS-Checks für PLM-Daten" --skills "Validierung,CATIA,Attribute"

# Neuen Agenten automatisch spawnen (ohne Bestätigung)
python -m atlas_run.atlas spawn "quality_checker" --desc "..." --auto

# Oder global
atlas "Schreibe einen IT Demand für Power Automate Premium" --agent demand_writer
```

---

## Agenten

| Agent | Spezialisierung |
|---|---|
| `plm_coordinator` | PLM-Koordination, CATIA, ENOVIA, SAP, P&ID, Prozessanalyse |
| `sr_writer` | Service Requests, Bug Reports, PLM-Systeme |
| `automation_engineer` | Python, Power Automate, VBA, Shell, Pipelines |
| `demand_writer` | IT Demands, Business Case, ROI, Management-Texte |
| `daily_briefing` | Tagesplanung, Prioritäten, Blocker |
| `+ dynamisch` | Neue Agenten entstehen bei unbekannten Task-Typen |

---

## Schwarm-Dateien

```
atlas_memory/
├── global/
│   ├── atlas_knowledge.md      # Globales Domänenwissen
│   ├── learnings.jsonl         # Destillierte Erkenntnisse aller Agenten
│   ├── skill_index.json        # Welcher Agent was kann
│   └── agent_registry.json     # Alle aktiven Agenten
├── blackboard/                 # Signale (Pheromone) zwischen Agenten
└── history/                    # Jeder Lauf als JSON

atlas_agents/<name>/
├── system.md                   # Rolle und Regeln
├── memory.md                   # Privates erlerntes Wissen
├── examples.md                 # Gute Beispiele
└── skills.md                   # Fähigkeiten
```

---

## Konfiguration (.env)

```env
OPENROUTER_API_KEY=your_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
ATLAS_DEFAULT_MODEL=minimax/minimax-m2.5
ATLAS_SPAWN_CONFIRM=true      # false = vollautomatischer Spawn
ATLAS_LEARN_AUTO=true         # false = kein automatisches Lernen
```

---

## Forschungs-Grundlage

- **Blackboard-Architektur**: LbMAS (arxiv 2507.01701), LLM Blackboard System (arxiv 2510.01285)
- **Stigmergy**: SwarmSys (arxiv 2510.10047), Pheromone-traces für LLM-Koordination
- **Dynamischer Spawn**: DRTAG — Dynamic Real-Time Agent Generation (NCBI PMC12465116)
- **Schwarm-Lernen**: Flexible Swarm Learning (arxiv 2510.06349)
