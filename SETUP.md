# Setup

This is a customized build of MARK XLVIII (JARVIS) with an added **Agent Mode**.

## 1. Provide your Gemini API key
Copy the example config and paste in your own key:

```
cp config/api_keys.example.json config/api_keys.json
```

Then edit `config/api_keys.json` and replace `YOUR_GEMINI_API_KEY_HERE` with your key
from https://aistudio.google.com/apikey. This file is git-ignored and never uploaded.

## 2. Install dependencies
```
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
pip install PyQt6 truststore
```

## 3. Run
```
python main.py
```
On Windows you can also double-click `Start-Jarvis.bat`.

## Agent Mode
`actions/agent_mode.py` adds an autonomous, Claude-style agent: given a goal, it reads
and edits files, runs shell commands, checks the output, and iterates until the task is
done (capped at 18 steps). It runs on the same Gemini API key. A destructive-command
blocklist refuses recursive/forced deletes, disk formatting, shutdown, and registry wipes.

JARVIS routes complex, multi-step computer tasks to it automatically; simple one-shot
actions still use the direct tools.

## Notes on TLS
This build uses `truststore` (via `.venv` `sitecustomize.py`) so Python trusts the OS
certificate store — needed on machines behind a TLS-inspecting proxy/AV. The dashboard's
self-signed cert/key are NOT included; they are generated locally on first run.
