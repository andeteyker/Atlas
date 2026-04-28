# ATLAS Global Knowledge Base

ATLAS ist ein domänen-agnostisches dezentrales Schwarm-AIOS.
Der Schwarm baut sich selbst auf — basierend auf dem Thema das du einbringst.

## Schwarm-Prinzipien

**Blackboard-Pattern:** Agenten hinterlassen Signale (Pheromone) bei Erkenntnissen,
Wissenslücken oder Delegationen. Andere Agenten reagieren autonom darauf.

**Stigmergy:** Häufig genutzte Lösungswege werden durch Lernsignale verstärkt.

**Auto-Lernen:** Nach jedem Lauf destilliert der Learner eine Regel →
private memory.md + globaler Pool + Vector Store (semantisches Dedup).

**Semantische Memory:** ChromaDB sucht relevante Erinnerungen semantisch
statt alles in den Kontext zu laden.

## Agenten-System

- Jeder Agent hat einen privaten Stack: system.md · memory.md · examples.md · skills.md
- Agenten delegieren Subtasks via Blackboard-Signal an Spezialisten
- Neue Agenten entstehen durch `atlas init`, `atlas spawn` oder automatisch beim ersten `atlas run`
- Der Swarm-Architekt (bootstrap.py) analysiert das Thema und erstellt ein optimales Team

## Arbeitsregeln (für alle Agenten)

- Trenne Fakten, Annahmen, Risiken und nächste Schritte klar
- Erfinde keine fehlenden Informationen — markiere Lücken mit `GAP: thema | grund`
- Delegiere mit: `DELEGATION: agent_name | subtask`
- Gib verwertbare, konkrete Ergebnisse — keine Allgemeinplätze
