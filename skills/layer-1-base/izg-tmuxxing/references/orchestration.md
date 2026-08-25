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
2. **Dateibereiche pruefen:** Fuer jedes gewaehlte Ticket den betroffenen
   Dateibereich bestimmen (Ticketbeschreibung / Titel). Zwei Tickets mit
   ueberlappendem Bereich NICHT im selben Durchgang an unterschiedliche Panes
   verteilen (Regel aus IZG-T-198). Diese Pruefung ist Handarbeit des Agenten und
   bleibt es — es gibt keine geplante Automatisierung dafuer.
   Ueberlappung sichtbar melden, nicht still serialisieren oder eines der beiden
   Tickets stillschweigend zurueckhalten.
3. **Vor dem Versand Status wechseln:** `bash scripts/tickets.sh move <ID>
   in-progress "An Pane %X verteilt" --by <agent>` ausfuehren. Schlaegt der
   Statuswechsel fehl, wird kein Auftrag verschickt. Das ist zugleich die Sperre
   gegen Doppelvergabe: das Ticket liegt danach nicht mehr in `tickets/open/` und
   taucht im Picker nicht mehr auf.
4. **Auftrag verschicken:** Pro Pane genau ein Auftrag pro Durchgang. Der
   Auftragstext nennt die Dateiabgrenzung gegenueber den parallel laufenden Panes
   explizit und schliesst "nicht committen" ein.
5. **Nachlegen ohne Polling:** `SendMessage` mit `notify_when_idle: true` statt
   den Pane-Status abzufragen. Beim Nachlegen: `/clear` im Zielpane, kurze Pause,
   dann der naechste Auftrag.
6. **Ueberhang behandeln:** Mehr gewaehlte Tickets als idle Panes → Ueberhang
   sichtbar melden, nicht verwerfen und nicht blind an ein bereits belegtes Pane
   schicken. Panes koennen legitim leer ausgehen, wenn die Dateibereiche das
   verlangen (Schritt 2).
7. **Ergebnisse pruefen:** Bevor ein Ticket auf `done` geht, das Ergebnis selbst
   verifizieren (Diff lesen, Akzeptanzkriterien pruefen). Der Abschlussbericht des
   Agenten allein ist kein Nachweis.

Nicht Teil dieses Playbooks: Dateikonflikte und Commits als solche — siehe Abschnitt
oben (IZG-T-198).
