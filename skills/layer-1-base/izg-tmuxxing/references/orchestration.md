# Parallelarbeit: Dateikonflikte und Commits (IZG-T-198)

Alle Panes teilen sich denselben Working-Tree derselben Checkout — der Kernkonflikt
bei mehreren gleichzeitig verteilten Tickets ist gleichzeitiges Schreiben derselben
Datei, kein Git-Merge-Problem. Gewaehlte Absicherung: **disjunkte Dateibereiche pro
Verteilrunde** (Tickets, die dieselben Dateien/Ordner betreffen, nicht im selben
Durchgang an unterschiedliche Panes verteilen), zusammen mit der bestehenden
Konvention, beim Commit gezielt einzelne Dateien zu stagen (`git add <datei>`, nie
`-A`/`.`) statt versehentlich fremde Aenderungen mit einzuchecken.

Verworfen: `git worktree` pro Pane (verlangt einen eigenen Branch je Worktree,
widerspricht der No-Branch-Konvention direkt auf main); ein reiner Commit-Lock
(loest nur die Symptom-Ebene, nicht das gleichzeitige Ueberschreiben derselben
Datei vor dem Commit).

Der Picker selbst warnt nicht bei ueberlappenden Dateibereichen und wird es auch
nicht tun — er verteilt seit IZG-T-195 gar nicht mehr selbst. Die Pruefung liegt
beim orchestrierenden Agenten, siehe Schritt 2 des Playbooks unten.

# Orchestrierungs-Playbook fuer verteilte Tickets (IZG-T-196)

Der Picker (IZG-T-195) uebergibt dem orchestrierenden Agenten nur die Ticket-Auswahl.
Alles Weitere — Ziel-Panes finden, Auftraege verschicken, nachlegen, pruefen — macht
der Agent selbst. Ablauf, Schritt fuer Schritt:

1. **Ziel-Panes ermitteln:** `ListAgents` aufrufen. Liefert je Peer-Session
   `busy`/`idle` und die tmux-Pane-Zuordnung. Kein `tmux list-panes`-Raten, kein
   Scrapen von `capture-pane` — Scraping ist unzuverlaessig: ein Vollbild-Kommando
   im Pane kann den Busy-Indikator verdecken, ein Watcher meldet dann faelschlich
   "fertig", obwohl der Agent noch arbeitet. Nur Sessions mit Status `idle` sind
   Kandidaten fuer einen Auftrag.
2. **Dateibereiche pruefen:** Der Orchestrator bestimmt den GESCHRIEBENEN
   Dateibereich pro Ticket selbst — aus den Akzeptanzkriterien, nicht aus der
   Ticket-Prosa. Prosa-Angaben zu betroffenen Dateien sind Hinweis, nicht
   Wahrheit: in der Runde IZG-T-206..209 stand in drei Tickets faelschlich,
   sie fassten dieselbe Datei an, was ein Pane grundlos leer gelassen haette
   (beobachtet in IZG-T-210). Lesend
   genutzte Pfade zaehlen fuer die Konfliktpruefung nicht mit. Ein eigenes
   Frontmatter-Feld dafuer (`writes:`) wurde erwogen und verworfen (IZG-T-210):
   der Fehler war eine falsche Vorhersage des Ticketautors, kein Formatproblem —
   ein strukturiertes Feld haette dieselbe falsche Vorhersage nur in ein anderes
   Feld verschoben, dafuer aber `tickets.sh` und die Ticket-Vorlage zusaetzlich
   belastet. Zwei Tickets mit ueberlappendem Bereich NICHT im selben Durchgang an
   unterschiedliche Panes verteilen (Regel aus IZG-T-198). Diese Pruefung ist
   Handarbeit des Agenten und bleibt es — es gibt keine geplante Automatisierung
   dafuer. Ueberlappung sichtbar melden, nicht still serialisieren oder eines der
   beiden Tickets stillschweigend zurueckhalten.
3. **Vor dem Versand Status wechseln:** `bash scripts/tickets.sh move <ID>
   in-progress "An Pane %X verteilt" --by <agent>` ausfuehren. Die Pane-ID im
   Verlaufstext ist verbindlich, nicht nur Beispieltext: `ListAgents` liefert
   keine Pane-zu-Ticket-Zuordnung, der Orchestrator haelt sie nur im Kopf, und
   nach einem Kontextverlust ist dieser Verlaufseintrag die einzige Stelle, aus
   der sie sich rekonstruieren laesst (IZG-T-210). Schlaegt der Statuswechsel
   fehl, wird kein Auftrag verschickt. Das ist zugleich die Sperre gegen
   Doppelvergabe: das Ticket liegt danach nicht mehr in `tickets/open/` und
   taucht im Picker nicht mehr auf.
4. **Vor dem Versand kurz pruefen, dann Auftrag verschicken:** Pro Pane genau
   ein Auftrag pro Durchgang. Ein bei IZG-T-206 vergessener Kaltstart-Hinweis
   liess sich nicht mehr nachtraeglich korrigieren, ohne einen Durchgang zu
   verbrennen — deshalb kurz gegenchecken, nicht um Vollstaendigkeit zu
   erzwingen, sondern um das Offensichtliche nicht zu vergessen: absolute Pfade?
   Abbruchbedingung benannt? Dateiabgrenzung gegenueber parallelen Panes
   explizit? "Nicht committen" enthalten, falls zutreffend? Die Checkliste
   ersetzt nicht das Mitdenken des Workers — bei IZG-T-207 hat der Worker selbst
   eine Luecke in der Zielstruktur gefunden und gemeldet, statt sie zu schlucken.
5. **Nachlegen ohne Polling:** `SendMessage` mit `notify_when_idle: true` statt
   den Pane-Status abzufragen. Beim Nachlegen: `/clear` im Zielpane, kurze Pause,
   dann der naechste Auftrag. Die `[Cross-session idle notice]`, die dabei
   eintrifft, ist kein Fertigmeldungsersatz — siehe Warnung in Schritt 7.
6. **Ueberhang behandeln:** Mehr gewaehlte Tickets als idle Panes → Ueberhang
   sichtbar melden, nicht verwerfen und nicht blind an ein bereits belegtes Pane
   schicken. Panes koennen legitim leer ausgehen, wenn die Dateibereiche das
   verlangen (Schritt 2).
7. **Ergebnisse pruefen:** Bevor ein Ticket auf `done` geht, das Ergebnis selbst
   verifizieren (Diff lesen, Akzeptanzkriterien pruefen). Der Abschlussbericht des
   Agenten allein ist kein Nachweis.

   **WARNUNG (IZG-T-210):** Die `[Cross-session idle notice]` fasst den
   ZULETZT abgeschlossenen Turn zusammen — bei einem Folgeauftrag an dieselbe
   Session bleibt sie auf dem vorherigen Auftrag stehen. Real aufgetreten:
   nach Versand von IZG-T-207 meldete die Notice noch das Ergebnis von
   IZG-T-206, zweimal in derselben Runde. Die Notice bedeutet nur "diese
   Session ist wieder frei", nicht "der zuletzt verschickte Auftrag ist
   fertig". Nur der Meldetext des Workers selbst zaehlt als Abnahmesignal —
   deshalb im Auftragstext verlangen, dass die Fertigmeldung mit der
   Ticket-ID beginnt, und ohne diesen Meldetext kein Ticket auf `done` setzen.

Nicht Teil dieses Playbooks: Dateikonflikte und Commits als solche — siehe Abschnitt
oben (IZG-T-198).
