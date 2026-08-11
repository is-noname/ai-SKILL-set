# ADR-20260811-001: Globale Konventionen bleiben Pointer-Includes, werden nicht zu Skills

## Kontext

`~/.claude/CLAUDE.md` band bis 2026-08-04 drei Konventionsdateien (`tickets.md`,
`doc-ids.md`, `design-tokens.md`) per `@`-Include vollständig in den Startkontext jeder
Session in jedem Projekt — zusammen ~3.600 Token, obwohl davon am Sessionstart fast
nichts gebraucht wird. Die Client-Seite wurde am 2026-08-04 bereits auf einen
3-Zeilen-Kern pro Konvention plus Pfadverweis umgestellt (`@`-Include entfernt, Datei
bleibt zum Nachlesen bei Bedarf liegen). IZG-T-081 bringt `setup_global_conventions.sh`
auf denselben Zustand.

Offene Frage (IZG-T-080, AK2): Ist der Pointer-Mechanismus die richtige Zielstruktur,
oder gehören die Konventionen stattdessen als Skills ausgeliefert
(`~/.claude/skills/ticketsystem/`, `.../doc-ids/`, `.../design-tokens/`), wo jede nur
eine Description-Zeile in der Skill-Liste kostet statt eines Blocks im Startkontext?

## Entscheidung

Der Pointer-Mechanismus (kurzer Regelblock + Pfadverweis in `CLAUDE.md`, volle Datei nur
bei Bedarf gelesen) bleibt bestehen. Keine Umstellung auf Skills.

## Begründung

1. **Die kritischen Laufzeitregeln müssen ohnehin im Startkontext bleiben.** Die
   Anti-`mv`-Regel für Tickets muss greifen, bevor der Agent zum ersten Mal eine
   Ticketdatei anfasst — das kann die dritte Nachricht einer frischen Session sein, lange
   bevor ein Skill kontextabhängig geladen würde. Ein Skill ersetzt den Pointer-Block
   also nicht, er würde ihn nur ergänzen — die Kernregeln blieben so oder so inline
   (siehe bereits umgesetzter Block in `~/.claude/CLAUDE.md`, Abschnitt „Ticketsystem").

2. **Der Pointer-Block ist schon fast so billig wie eine Skill-Description.** Nach der
   Umstellung vom 2026-08-04 kostet jede Konvention noch 3–6 Zeilen (~50–100 Token) statt
   eines vollständigen Includes. Die verbleibende Ersparnis einer Skill-Umstellung wäre
   marginal, während die Komplexität wächst: drei zusätzliche Skill-Pakete, die mit den
   Master-Dateien in `~/.claude` synchron gehalten werden müssten.

3. **Mehr Skills verschärfen den Befund aus AK4, statt ihn zu lindern.** Das
   Architektur-Review vom 2026-08-11 hat selbst festgestellt, dass die Skill-Liste
   bereits ~3.100 Token Startkontext über 37 Skill-Descriptions kostet. Drei weitere
   Skills nur für Konventionstext würden diesen Posten weiter aufblähen — das
   Kosten-Problem würde von „Include-Block" nach „Skill-Listeneintrag" verschoben, nicht
   gelöst.

4. **Skills passen semantisch nicht.** Ein Skill wird bei Bedarf für eine Aufgabe
   geladen (z. B. „Diagramm erstellen"). Konventionen wie Dokument-IDs oder Design-Tokens
   sind aber Hintergrundwissen, das beiläufig während anderer Arbeit gebraucht wird —
   kein eigener Trigger-Anlass, der eine Skill-Beschreibung rechtfertigen würde.

## Konsequenzen

- Der Pointer-Mechanismus aus IZG-T-081 ist die Zielarchitektur, nicht ein Zwischenschritt.
- Weitere Token-Einsparungen im Startkontext müssen an der Skill-Liste selbst ansetzen
  (Bereinigung, kürzere Descriptions — siehe IZG-T-080 AK4), nicht an einer
  Skill-Umwandlung der Konventionen.
- Falls künftig doch eine Konvention wirklich nur bei einem klar abgrenzbaren Anlass
  gebraucht wird (nicht beiläufig), kann sie einzeln neu bewertet werden — diese
  Entscheidung gilt für die drei genannten Konventionen als Gruppe, nicht als
  Dauerverbot für Skills generell.

## Bezug

- Ticket: IZG-T-080 (AK2)
- Umsetzung des Pointer-Zustands: IZG-T-081
- Skill-Listen-Bereinigung: IZG-T-080 (AK4)
