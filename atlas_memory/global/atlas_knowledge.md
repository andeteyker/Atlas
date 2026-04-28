# ATLAS Global Knowledge Base
*Domänenwissen für den ATLAS Schwarm — Schiffbau PLM Coordination*

---

## Arbeitskontext

**Organisation:** PLM Business Coordination, Schiffbau
**Kernaufgaben:** PLM-Systembetreuung, Prozessoptimierung, User Support, Automatisierung, Dokumentation

**Systeme im Einsatz:**
- CATIA V6 / 3DEXPERIENCE (CAD, Assembly, Drawing Management, P&ID)
- ENOVIA (Change Management, ECR/ECO, Lifecycle States, Maturity Level)
- SAP (MM/PM Module, Materialstamm, Instandhaltungsaufträge)
- Power Automate / Power BI (Automatisierung, Reporting)
- MS Teams / SharePoint (Kollaboration, Dokumentenmanagement)

---

## PLM-Grundregeln

### Priorisierung
- Blocking-Bugs → immer **PRIORITY High**, unabhängig von Frequency und Nutzeranzahl
- Klassifikations-relevante Fehler (DNV/Lloyd's) → immer **PRIORITY Critical**
- Stundensatz PLM-Team für ROI-Berechnungen: **62,40 €/h**
- Standard-Arbeitsjahr: 220 Tage × 8h = 1.760h

### Change Management
- ECR (Engineering Change Request) → ECO (Engineering Change Order) → Implementierung
- Change-Freeze gilt immer 4 Wochen vor Klassifikationsbesuchen
- Alle Changes müssen im ENOVIA ECO-Prozess dokumentiert sein
- JLM-Nummern: immer mit SAP-Materialstamm rückverfolgen

### Attribute & Produktstruktur
- Pflichtattribute je nach Schiffstyp variieren (Deckbuch vs. Maschinenraum)
- Bei unklaren Attributen: zuerst ENOVIA Maturity State prüfen
- Item-ID-Format: [Schiff]-[System]-[Laufnummer] (z.B. SH01-HVAC-00123)
- JLM-Nummern werden SAP-seitig als Materialstamm angelegt

### P&ID-Regeln
- Pfeile zeigen Strömungsrichtung — falsche Richtung = Critical Bug
- Linientypen: durchgezogen = Hauptleitung, gestrichelt = Hilfslinie
- Revisionsstand muss in Titelblock und Dateiname übereinstimmen
- P&ID-Freigabe: min. 2 Reviewer (Ingenieur + PLM Coordinator)

---

## Schwarm-Prinzipien

**Blackboard-Pattern:** Agenten hinterlassen Signale (Pheromone) bei Erkenntnissen, Lücken oder Delegationen. Andere Agenten reagieren autonom darauf.

**Stigmergy:** Positive Verstärkung: Häufig genutzte Lösungswege werden durch Lernsignale verstärkt.

**Auto-Lernen:** Nach jedem Lauf destilliert der Learner eine Regel → private memory.md + globaler Pool + Vector Store.

**Semantische Memory:** ChromaDB sucht relevante Erinnerungen semantisch statt alles zu laden.

---

## Agenten-Überblick

| Agent | Spezialisierung | Delegiere wenn... |
|-------|----------------|-------------------|
| `plm_coordinator` | PLM-Koordination, CATIA, ENOVIA, SAP, P&ID | Zentrale Anlaufstelle |
| `sr_writer` | Service Requests, Bug Reports, Incident | Konkreter Bug/Fehler zu dokumentieren |
| `automation_engineer` | Python, Power Automate, VBA, Shell | Code/Automatisierung gefragt |
| `demand_writer` | IT Demands, Business Case, ROI | Management-Vorlage nötig |
| `daily_briefing` | Tagesplanung, Prioritäten, Briefings | Tagesorganisation |

---

## Häufige Aufgaben & Lösungsansätze

### CATIA-Probleme
- Absturz beim Öffnen → Lizenzserver-Verbindung prüfen, dann Support
- Falsche Darstellung in Drawing → CATDrawing neu generieren, Referenzen prüfen
- Performance-Probleme → Modellgröße reduzieren, Tessellierung erhöhen

### ENOVIA-Probleme
- State-Transition schlägt fehl → Berechtigungen prüfen (Route + Business Rule)
- Attribut nicht sichtbar → Mask/Policy in ENOVIA Studio prüfen
- ECO steckt im Workflow → Admin-Eskalation + Business Rule Audit

### SAP-Integration
- JLM-Nummer nicht in SAP → Materialstamm noch nicht angelegt, PLM-Admin kontaktieren
- Rückverfolgbarkeit fehlt → Batch-Job zur Synchronisation anstoßen

### Power Automate
- Flow schlägt fehl → Connector-Verbindung prüfen, Token erneuern
- SharePoint-Trigger nicht aktiv → Webhook registrieren, Trigger reaktivieren

---

## Wissenslücken (bekannte offene Fragen)

- Exakte API-Endpunkte für ENOVIA 3DX R2024x: noch nicht vollständig dokumentiert
- SAP-PM-Schnittstelle: Custom RFC-Mapping je nach Installation
- Klassifikationsanforderungen Schiffstyp X: in Abstimmung mit Klassifikationsgesellschaft

---

## Abkürzungen & Definitionen

| Kürzel | Bedeutung |
|--------|-----------|
| PLM | Product Lifecycle Management |
| ECR | Engineering Change Request |
| ECO | Engineering Change Order |
| JLM | Jotun Lifecycle Management (interne Nummer) |
| P&ID | Piping & Instrumentation Diagram |
| 3DX | 3DEXPERIENCE (Dassault Systèmes) |
| SR | Service Request |
| PT | Personentag (8h) |
| DNV | Det Norske Veritas (Klassifikationsgesellschaft) |
| BV | Bureau Veritas (Klassifikationsgesellschaft) |
