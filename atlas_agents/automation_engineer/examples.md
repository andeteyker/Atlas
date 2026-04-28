Input: Erstelle eine Automation die tägliche Notizen und E-Mails in ein JSON-Briefing schreibt.

Output:
Ziel: Tägliches Briefing aus lokalen Notizen + Outlook-Export automatisch generieren.
Datenquellen: ~/notes/daily/*.md, Outlook CSV-Export
Ablauf: Notizen lesen → E-Mails parsen → JSON zusammenführen → Briefing-Agent triggern

Python-Prototyp:
```python
import json, glob
from datetime import date

notes = []
for f in glob.glob("~/notes/daily/*.md"):
    notes.append(open(f).read())

briefing = {"date": str(date.today()), "notes": notes, "emails": []}
with open("briefing.json", "w") as f:
    json.dump(briefing, f, ensure_ascii=False, indent=2)
```

Risiken: E-Mail-Export manuell — Power Automate Connector für vollständige Automatisierung empfohlen.
