# App-Prüfung & Parameter-Erkennung

Referenz für die beiden Pflicht-Checks vor dem Icon-Bau sowie zum Ermitteln der
Launcher-Parameter aus einer beliebigen Server-App.

## 1. Parameter aus der App ermitteln

`make_starter_icon.py` braucht: `--name`, `--workdir`, `--start`, optional
`--port`, `--url`, `--match`, `--icon`.

So aus dem Projekt herauslesen:

| Parameter | Wo finden |
|-----------|-----------|
| `--workdir` | Projektordner (wo der Startbefehl ausgeführt wird) |
| `--start` | README / package.json `scripts.start` / `if __name__ == "__main__"` / Streamlit-/Flask-Run-Zeile |
| `--port` | Code-Konstante (`app.run(port=...)`, `--server.port`, `PORT=`), README, `.env` |
| `--url` | meist `http://localhost:<port>` (Streamlit/Flask/FastAPI/Node). Default wird automatisch gesetzt |
| `--match` | eindeutiges Fragment des Startbefehls für `pkill -f` (z.B. Skriptname `app.py`). Default = Startbefehl |

Typische Startbefehle:

- Flask: `python3 app.py` oder `flask run --port 5000`
- FastAPI/Uvicorn: `uvicorn main:app --port 8000`
- Streamlit: `streamlit run app.py --server.port 8501 --server.headless true`
- Node/Express: `node server.js` oder `npm start`
- Vite/Next Dev: `npm run dev`

Bei Streamlit `--server.headless true` ergänzen, damit Streamlit nicht selbst
einen zweiten Browser-Tab öffnet (der Launcher öffnet den Browser bereits).

## 2. Pflicht-Check A: App hat einen "Beenden"-Button

Server-Apps laufen nach dem Schließen des Browser-Tabs im Hintergrund weiter.
Darum muss die App einen sichtbaren Weg zum Beenden des Servers haben. Vor dem
Icon-Bau prüfen, ob ein solcher existiert; falls nicht, ergänzen.

**Akzeptanzkriterium:** Es gibt einen klar beschrifteten Button ("Beenden" /
"App schließen"), der den Server-Prozess stoppt (nicht nur den Tab).

### Flask / FastAPI — Shutdown-Endpoint

```python
import os, signal, threading

@app.post("/shutdown")
def shutdown():
    # Antwort senden, dann Prozess beenden
    threading.Timer(0.5, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
    return "Beendet. Fenster kann geschlossen werden."
```

Im Frontend ein Button, der `/shutdown` per POST aufruft und danach
`window.close()` versucht.

### Streamlit — Beenden-Button

```python
import os, signal
if st.sidebar.button("App beenden"):
    st.write("App wird beendet ...")
    os.kill(os.getpid(), signal.SIGTERM)
```

### Node/Express

```js
app.post("/shutdown", (req, res) => {
  res.send("Beendet.");
  setTimeout(() => process.exit(0), 300);
});
```

Wenn ein Beenden-Mechanismus fehlt: dem Nutzer kurz melden und den passenden
Endpoint + Button ergänzen. Der Launcher beendet beim **nächsten** Start zwar
ohnehin alte Instanzen (über Port/Pattern), ersetzt aber keinen bewussten
Beenden-Button in der App.

## 3. Pflicht-Check B: Kein hängenbleibendes Terminalfenster

Der generierte Launcher startet den Server mit `setsid`/`disown` losgelöst und
schreibt Logs in `~/.local/share/izg-starter/logs/<slug>.log`. Das `.desktop`
wird mit `Terminal=false` erzeugt — es öffnet sich **gar kein** Terminal.

Nur wenn Logs sichtbar gebraucht werden, mit `--show-terminal` bauen: dann
schließt der Launcher das Terminalfenster nach dem Start selbst per `xdotool`
(soweit die Desktop-Umgebung das zulässt; unter Wayland eingeschränkt).

Wenn die App selbst beim Start ein Terminal aufmacht (z.B. ein vorhandenes
Start-Skript ruft `gnome-terminal -- ...`), dieses im Startbefehl entfernen und
stattdessen den reinen Server-Befehl an `--start` übergeben.

## 4. Verifikation nach dem Bau

```bash
# Syntax des Launchers prüfen
bash -n ~/.local/bin/<slug>-launcher.sh
# .desktop validieren (optional, falls desktop-file-utils installiert)
desktop-file-validate ~/Schreibtisch/<Name>.desktop
```

Cinnamon/Nemo zeigt ein neues `.desktop` evtl. erst als Textdatei. Das Skript
setzt `metadata::trusted=true` via `gio`; falls das Icon trotzdem nicht startet:
einmal Rechtsklick → "Starten erlauben".
