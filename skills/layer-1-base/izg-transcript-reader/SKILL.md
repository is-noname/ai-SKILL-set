---
name: izg-transcript-reader
description: Gemeinsamer Adapter fuer das undokumentierte Claude-Code-Transcript-Format (~/.claude/projects/<slug>/*.jsonl). Kein eigenstaendig aufrufbarer Skill, sondern Formatwissen-Baustein fuer Skills, die Transcripts auswerten.
layer: 1
dependencies: []
disable-model-invocation: true
---

# izg-transcript-reader

Kapselt das undokumentierte Claude-Code-Transcript-Format an einer einzigen
Stelle, damit ein Formatwechsel an genau dieser Stelle sichtbar bricht -
nicht still in mehreren Skills gleichzeitig mit unterschiedlichen Zahlen.

Kein Skill mit eigenem Ablauf. Wird von anderen Skills als Dependency gezogen
und importiert (`scripts/transcript.py`).

## Interface

Auffinden:

- `project_slug(path) -> str`
- `transcript_path(project, session_id) -> Path` - Pfad einer einzelnen Session.
- `find_transcripts(project, limit, session=None, base_dir=None) -> list[Path]`
  - juengste Sessions eines Projekts, optional auf eine Session gefiltert.

Lesen:

- `read_session(path, session_id) -> SessionUsage` - eine Session komplett
  eingelesen und aggregiert (Requests, Usage-Summe, Tool-Aufrufe,
  Tool-Result-Tokens, genutzte Skills, Subagent-Output, Zeitspanne).
- `read_entries(files, since=None, until=None) -> Iterator[dict]` - rohe,
  geparste JSONL-Eintraege ueber mehrere Dateien, optional zeitlich gefiltert.
- `parse_entries(entries) -> ParsedTranscript` - Eintraege zu den rohen
  Bausteinen verdichtet (usage_by_request, tool_calls, result_chars,
  calls_per_tool, label_counts, skills_used, sidechain_output_tokens,
  timestamps). Fuer Auswertungen ueber mehrere Sessions, bei denen die
  Aggregation (Gruppierung, Wiederholungszaehlung, Findings) beim
  aufrufenden Skill bleibt.

Hilfsfunktionen:

- `content_len(content) -> int` - Zeichenlaenge, egal ob str/list/dict.
- `call_label(name, params) -> str` - kurzer, gruppierbarer Bezeichner fuer
  einen Tool-Call (Formatwissen ueber Tool-Parameter, nicht ueber Tokens).
- `usage_totals(usage_by_request) -> dict[str, int]`
- `estimate_tool_tokens(tool_calls, result_chars) -> list[dict]`
- `CHARS_PER_TOKEN` - grobe Schaetzung fuer Tool-Result-Payloads.

## Einbinden

Nach dem Pull liegen Skills flach nebeneinander (`.claude/skills/<name>/`),
im Repo dagegen verschachtelt nach Layer. Ein fester relativer Import haelt
nur in einer der beiden Welten - konsumierende Skills loesen den Pfad daher
zur Laufzeit auf (erst Zielprojekt-Layout, dann Repo-Layout, sonst klare
Fehlermeldung).

Der Bootstrap dafuer ist in jedem konsumierenden Skill wortgleich und muss es
bleiben: er laeuft zwangslaeufig *vor* jedem Import aus diesem Skill und kann
daher nicht hierher wandern (IZG-T-146). Alles danach steht in `scripts/locate.py`:

```python
# ... Bootstrap: Kandidatenpfade pruefen, sys.path setzen ...
import locate as _locate

_t = _locate.re_export(globals(), ["CHARS_PER_TOKEN", "find_transcripts"])
```

- `load(name="transcript") -> module` - laedt ein Modul dieses Skills unter
  eindeutigem sys.modules-Namen. Noetig, weil ein konsumierender Shim selbst
  `transcript.py` heissen darf, ohne sich beim Import selbst zu treffen.
- `re_export(namespace, names, module=None) -> module` - uebernimmt die
  genannten Namen ins Aufrufer-Namespace und meldet Interface-Drift als
  ImportError statt als spaeteres AttributeError.

Vorlage zum Kopieren: der Bootstrap-Block in `scripts/transcript.py`
(`izg-benchmark-actions`) bzw. `scripts/analyze_transcript.py`
(`izg-improve-token-usage`).
