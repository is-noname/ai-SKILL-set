# ADR-20260814-001: Report-Stil bleibt pro Skill frei, kein geteiltes Modul

## Kontext

`izg-improve-token-usage` deklarierte im Frontmatter `html-report-template` als
Dependency, obwohl `HTML-REPORT.md` woertlich das Gegenteil sagte: der globale
Skin sei Dark-Mode und passe nicht zu den Balken- und Vorher/Nachher-Vergleichen
des Skills. `pull_skill.py` loest Dependencies transitiv auf und zog dadurch in
jedes Zielprojekt einen Skill mit, den der Ablauf nie benutzt (IZG-T-138).

Der Widerspruch wirft die eigentliche Frage auf: soll HTML-Report-Stil im Repo
ein geteiltes Modul sein (`html-report-template` als Pflicht-Skin fuer alle
Report-Skills), oder darf jeder Report-Skill sein eigenes Aussehen definieren?

## Entscheidung

Report-Stil ist pro Skill frei. `html-report-template` ist ein Angebot fuer
Skills, die keinen eigenen Skin brauchen — keine Pflicht-Abhaengigkeit fuer alle
Report-erzeugenden Skills. `izg-improve-token-usage` deklariert es nicht mehr
als Dependency und beschreibt seinen eigenen Skin vollstaendig in
`HTML-REPORT.md`.

## Begruendung

1. **Der bestehende Skin ist inhaltlich begruendet, nicht Geschmackssache.**
   `HTML-REPORT.md` erklaert explizit, warum der globale Skin nicht passt: Dark
   Mode kollidiert mit den Rot/Gruen-Verbrauchsbalken und Vorher/Nachher-
   Vergleichen, die die Kernaussage des Reports tragen. Eine erzwungene
   Vereinheitlichung wuerde eine funktionale Entscheidung einer stilistischen
   unterordnen.

2. **Eine deklarierte, aber ignorierte Dependency ist schlechter als keine.**
   Sie zieht Skill-Dateien in Zielprojekte, ohne dass der Ablauf sie je
   aufruft — Tokenlast ohne Ertrag, der Fehler, den dieser Skill bei anderen
   Stellen aufspueren soll.

3. **`html-report-template` bleibt fuer Skills sinnvoll, die keinen eigenen
   Skin brauchen.** Die Entscheidung ist keine Abschaffung des Templates,
   sondern macht seine Nutzung optional statt einer Pflicht-Transitivitaet
   ueber Dependency-Aufloesung.

## Konsequenzen

- `dependencies` in `izg-improve-token-usage/SKILL.md` enthaelt
  `html-report-template` nicht mehr; `registry.json` wurde neu generiert.
- Andere Report-Skills muessen ihren Skin-Bezug im eigenen SKILL.md/Report-Doc
  explizit machen (Template nutzen oder eigenen Skin begruenden) statt es
  stillschweigend offen zu lassen.
- Kuenftige Architektur-Reviews, die eine Vereinheitlichung des Report-Stils
  vorschlagen, finden hier die bereits gepruefte Gegenposition.

## Bezug

- Ticket: IZG-T-138
