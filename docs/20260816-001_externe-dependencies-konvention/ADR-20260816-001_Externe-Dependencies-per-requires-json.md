# ADR-20260816-001: Externe Voraussetzungen als `requires.json` je Skill

## Kontext

Ein gepullter Skill konnte stillschweigend unbrauchbar sein, weil eine externe
Voraussetzung auf der Zielmaschine fehlte — ein Kommando, ein API-Key, ein
Python-Paket. Es gab weder Deklaration noch Pruefung: der Fehler fiel erst beim
Ausfuehren auf, oft mitten in einer Session. Betroffen waren `agentmail`
(API-Key), `izg-starter-icon-mkr` (`xdg-utils`, Desktop-Umgebung) und
`izg-decision-sheet` (`xdg-open`).

Der Punkt stand seit 2026-06-22 offen ("Konvention wenn ein Skill eine global
installierte Dependency braucht") und wurde als IZG-T-073 gefuehrt. Ziel war
ausdruecklich die idiotensichere Variante: der Nutzer soll nicht selbst
herausfinden muessen, was fehlt.

## Entscheidung

Externe Voraussetzungen werden in einer `requires.json` neben der `SKILL.md`
deklariert — als Liste typisierter Eintraege (`cmd`, `env`, `py`, `file`) mit
`hint` (wie behebt man es) und `optional` (laeuft der Skill eingeschraenkt
weiter). `generate_registry.py` inlined sie in `registry.json`, `pull_skill.py`
prueft sie nach jedem Pull und Update und bietet ein optionales, skill-eigenes
`setup.sh` an. `pull_skill.py doctor` prueft nachtraeglich alle installierten
Skills.

`setup.sh` wird **nie ungefragt** ausgefuehrt, nur bei explizitem `--setup`.

## Begruendung

1. **Eigene Datei statt Frontmatter-Feld.** Der Frontmatter-Parser in
   `generate_registry.py` ist zeilenbasiert und kann nur Skalare und flache
   String-Listen. Strukturierte Eintraege mit `hint` und `optional` haetten
   entweder eine Mini-DSL (`"env:KEY|Hinweis|optional"`) oder einen echten
   YAML-Parser erfordert. Eine JSON-Datei kostet nichts und laesst den
   fragilen Parser in Ruhe.

2. **`hint` ist der eigentliche Kern, nicht die Deklaration.** "Idiotensicher"
   heisst nicht "es wird gemeldet", sondern "der naechste Schritt steht daneben".
   Eine reine Existenzpruefung ohne Fix-Hinweis waere nur eine hoeflichere Form
   des Status quo.

3. **`optional` verhindert Fehlalarm-Muedigkeit.** `izg-decision-sheet` laeuft
   ohne `xdg-open` weiter und nennt den Pfad zum manuellen Oeffnen. Wuerde das
   als Fehler gemeldet, lernte der Nutzer, den Block zu ueberspringen — und
   uebersaehe dann auch die echten.

4. **Deklaration und `setup.sh` sind komplementaer, nicht alternativ.** Ein
   `setup.sh` allein (die urspruengliche Auswahl im Decision-Sheet) haette
   keinen Aufhaenger fuer nachtraegliche Pruefung: es weiss nicht, ob es noetig
   ist, und `doctor` haette nichts zu pruefen. Die Deklaration allein loest
   dagegen nichts. Deklaration entscheidet **ob**, `setup.sh` erledigt **wie**.

5. **`setup.sh` nur auf Ansage.** Ein Skill-Pull, der ungefragt fremde Scripts
   ausfuehrt und Pakete installiert, ist ein Einfallstor. Der Komfortgewinn
   waere ein Flag (`--setup`) gross, das Risiko dauerhaft.

## Konsequenzen

- Neue Skills mit externer Voraussetzung deklarieren sie in `requires.json` —
  Konvention in `skills/README.md` verankert. Prosa im SKILL.md gilt nicht mehr
  als ausreichend.
- Eine kaputte `requires.json` laesst `generate_registry.py` und damit den
  Pre-Commit-Hook scheitern.
- `pull_skill.py doctor` ist neu; Exit-Code 1 bei fehlender Pflicht-Voraussetzung
  macht ihn CI-tauglich.
- Nebenbefund derselben Arbeit: eine `.env` im Skill-Verzeichnis wurde bisher
  von `copytree` in jedes Zielprojekt kopiert — der agentmail-API-Key waere
  mitgewandert. `.env` ist jetzt vom Pull und vom Update-Digest ausgenommen; das
  Zielprojekt bekommt seine eigene ueber `setup.sh`.
- `env`-Pruefungen sehen bewusst auch in die skill-eigene `.env`, nicht nur in
  die Shell-Umgebung — sonst gaelte eine korrekt eingerichtete
  agentmail-Installation als kaputt.

## Bezug

- Ticket: IZG-T-073
- Konvention: `skills/README.md`, Abschnitt "Externe Voraussetzungen"
