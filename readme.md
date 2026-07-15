# 🧙‍♂️ JARVIS — Mark XLVIII · Agent + Spells Fork

A voice-driven desktop assistant for **Windows, macOS, and Linux**. It listens, talks
back, watches your screen and webcam when asked, and takes real actions on your
computer — all in real time through Google's **Gemini Live API**. No monthly
subscription, no cloud middleman: you bring your own Gemini key and everything runs
locally against Google's endpoint.

This repository is a **customized fork** of the original MARK XLVIII. On top of the
base assistant it adds three things: an autonomous **Agent Mode** that does real
multi-step work, a **Harry Potter spellbook** of voice commands, and a **quieter
startup** that greets you instead of reading the news. Full credit to the original
author is below — please keep it intact.

---

> ## 🙏 Attribution & Credits
> This project is a **modified fork** of **MARK XLVIII by FatihMakes**.
> - **Original repository:** https://github.com/FatihMakes/Mark-XLVIII
> - **Creator:** FatihMakes — [YouTube](https://www.youtube.com/@FatihMakes) · [Instagram](https://www.instagram.com/fatihmakes)
> - **License:** [Creative Commons Attribution–NonCommercial 4.0 (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/)
>
> All original credit belongs to FatihMakes. This fork is a **non-commercial** personal project.
> As required by CC BY-NC 4.0, this work may **not** be used commercially, and this attribution
> and license must be preserved in any redistribution.

---

## 📑 Table of contents

1. [What this fork adds](#-what-this-fork-adds)
2. [Agent Mode in depth](#-agent-mode-in-depth)
3. [The spellbook](#-the-spellbook)
4. [Inherited capabilities](#-inherited-capabilities)
5. [How it works](#-how-it-works)
6. [Quick start](#-quick-start)
7. [Talking to JARVIS](#-talking-to-jarvis)
8. [Project structure](#-project-structure)
9. [Privacy & what stays local](#-privacy--what-stays-local)
10. [Troubleshooting](#-troubleshooting)
11. [License](#-license)

---

## ✨ What this fork adds

| Addition | What it does |
|---|---|
| 🤖 **Agent Mode** | An autonomous worker that reads/edits files, runs commands, checks results, and iterates until a task is genuinely finished — not a one-shot reply. |
| 🪄 **Spellbook** | Cast **22 Harry Potter incantations** by voice to open/close apps, control light and sound, lock the screen, screenshot, clear the clipboard, and more. |
| 📊 **Market analysis** | Read-only technical analysis of crypto from Delta Exchange's public data — price, trend, RSI, MACD, EMAs, ATR, and a bias call. Analysis only; it never trades. |
| 🎥 **Video analysis** | Point JARVIS at a YouTube URL or topic and it pulls the transcript and gives a real breakdown — overview, key points, claims, and a critical read. |
| 🔕 **Quiet startup** | JARVIS greets you and then waits. News and briefings arrive only on request, never automatically at launch. |

Everything else from the base assistant — voice chat, vision, OS control, file
management, reminders, memory, the phone dashboard — is still here and unchanged.

---

## 🤖 Agent Mode in depth

Ordinary assistant commands are single actions: "open Chrome", "what's the CPU usage".
**Agent Mode** is for the jobs that take several steps and some judgement — the kind of
thing you'd normally do yourself with a terminal and an editor open.

You give it a goal in plain language and it works the problem end to end:

- **Investigate** — it lists folders and reads files to understand the situation before
  changing anything.
- **Act** — it writes and edits files, and runs shell commands.
- **Verify** — it runs what it built and reads the output.
- **Iterate** — if something fails, it reads the error, fixes it, and tries again.

It keeps going until the task is done or it decides it's genuinely blocked, then reports
back in plain language. The loop is capped at **18 rounds** so it can never spin forever
and burn your quota.

**Safety.** Because it can run real commands, a destructive-command guard refuses the
catastrophic ones — recursive or forced deletes, disk formatting, system shutdown, and
registry wipes are blocked before they run. Everyday file edits and commands run freely.

**Cost.** Agent Mode runs on the **same Gemini key** as the rest of JARVIS, so it stays
on your existing free/generous quota. It is Gemini's reasoning driving the loop, styled
to work thoroughly and push through obstacles.

**Routing.** You don't have to name it — JARVIS sends complex, multi-step computer work
to the agent on its own, and keeps quick one-off actions on the fast direct tools. If it
ever misjudges, saying "use agent mode for this" forces it.

**Examples of what to ask:**

- "Go through my project folder and tell me what each file does."
- "Create a folder on my Desktop, add three notes, and list them back."
- "Fix the import error in this script and run it to confirm."
- "Set up a virtual environment here and install the requirements."

---

## 🪄 The spellbook

Speak the incantation and JARVIS obeys.

| Say | Effect |
|---|---|
| `Accio <app>` | Summon (open) an app — e.g. *Accio Chrome*, *Accio Spotify* |
| `Avada Kedavra <app>` | Strike down (close) that app's process — e.g. *Avada Kedavra Notepad* |
| `Expecto Patronum` | Summon a guardian — open Task Manager |
| `Expelliarmus` | Disarm — close the active window |
| `Wingardium Leviosa` | Levitate the windows away — show the desktop |
| `Lumos` / `Incendio` | Brightness up |
| `Nox` / `Glacius` | Brightness down |
| `Silencio` | Mute the sound |
| `Sonorus` / `Crescendo` | Volume up |
| `Quietus` | Volume down |
| `Colloportus` / `Stupefy` | Lock the screen |
| `Protego` | Raise a shield — enable the screensaver |
| `Alohomora` | Unlock the display from sleep — keep it awake |
| `Finite Incantatem` | End active effects — allow sleep again |
| `Tempus` | Conjure the current time aloud |
| `Obliviate` | Memory charm — wipe the clipboard |
| `Geminio` | Duplication charm — copy the selection |
| `Revelio` | Reveal — take a screenshot to the Desktop |
| `Reparo` | Mend the Windows desktop / taskbar (restart Explorer) |

`Accio` reuses the assistant's built-in app launcher, so all its known apps (browsers,
editors, chat apps, media players, Office, and more) work by their friendly names.

**Safety.** `Avada Kedavra` will not touch protected system processes — the shell,
window manager, core Windows services, and JARVIS itself are shielded, so a stray spell
can't crash your machine. It only ends normal user applications.

---

## 🧰 Inherited capabilities

From the original MARK XLVIII, all still available:

| Capability | Description |
|---|---|
| 🎙️ Real-time voice | Low-latency spoken conversation in your language via Gemini Live |
| 👁️ Vision | Reads your screen and webcam on request and reasons about what it sees |
| 🖥️ OS control | Volume, brightness, Wi-Fi, window management, shortcuts, power |
| 📂 File management | List, create, move, copy, rename, read, write, search, and open files |
| 🔍 Web search | News, research, price, and comparison modes — on demand |
| ⏰ Reminders | OS-native scheduled notifications |
| 🧠 Persistent memory | Remembers your preferences and context across sessions |
| 💻 Code helper & builder | Reviews code and scaffolds small projects |
| 📱 Remote dashboard | Control JARVIS from your phone's browser over the local network |
| 🌐 Browser control | Open URLs and drive tabs by voice |

---

## 🧩 How it works

JARVIS opens a streaming session to Gemini's native-audio model. Your microphone audio
is sent up in small chunks; Gemini transcribes, reasons, and streams speech back, all in
one live connection — that's what makes the conversation feel immediate.

Actions are exposed to the model as **tools** (function declarations). When you ask for
something, Gemini decides which tool to call and with what arguments; JARVIS executes it
locally and feeds the result back into the conversation. Agent Mode and the spellbook are
each just tools registered the same way, so the assistant can reach for them naturally
mid-conversation.

A PyQt heads-up display shows state (listening / thinking / speaking) and a content panel
for search results, while a small local web server powers the optional phone dashboard.

---

## 🚀 Quick start

```bash
# 1. Provide your Gemini API key (this file is git-ignored and never uploaded)
cp config/api_keys.example.json config/api_keys.json
#    then edit config/api_keys.json and paste your key from:
#    https://aistudio.google.com/apikey

# 2. Create an environment and install dependencies
python -m venv .venv
.venv\Scripts\activate            # Windows  (use: source .venv/bin/activate  on macOS/Linux)
pip install -r requirements.txt
pip install PyQt6 truststore

# 3. Run it
python main.py                    # or, on Windows, double-click Start-Jarvis.bat
```

More detail — including the TLS/trust-store note for machines behind an inspecting
proxy or antivirus — is in [`SETUP.md`](SETUP.md).

---

## 💬 Talking to JARVIS

Once it's running, just speak naturally. A few things to try:

- **Chat:** "What's the time?" · "Remind me to stretch in 20 minutes."
- **Control:** "Turn the volume down." · "Open VS Code."
- **Spells:** "Accio Chrome." · "Lumos." · "Revelio." · "Avada Kedavra Notepad."
- **Market:** "Analyze Bitcoin on the 1-hour." · "What's the price of ETH?" · "Give me a technical read on SOL daily."
- **Video:** "Analyze this YouTube video: <url>." · "Watch and break down the latest video on <topic>."
- **Agent work:** "Organize my Downloads folder and tell me what you moved."
- **On demand only:** "Give me today's top news." (it won't do this on its own anymore)

---

## 🗂️ Project structure

```
main.py                 Entry point: Gemini Live session, tool dispatch, HUD wiring
ui.py                   PyQt heads-up display
core/                   prompt.txt (assistant persona/rules), STT/TTS, installer, llm client
actions/                One module per capability:
  agent_mode.py           autonomous multi-step agent (this fork)
  spells.py               Harry Potter spellbook — 22 incantations (this fork)
  delta_market.py         read-only crypto TA from Delta Exchange (this fork)
  youtube_video.py        play + transcript-based video analysis (analyze added this fork)
  file_controller.py      file & folder operations (path + open fixes in this fork)
  open_app.py             app launcher with a large alias map
  computer_settings.py    volume, brightness, windows, power
  web_search.py, weather_report.py, reminder.py, ... and more
dashboard/              local web server + static assets for the phone remote
memory/                 persistent memory manager
config/                 api_keys.example.json, app icon
```

---

## 🔐 Privacy & what stays local

The following are **git-ignored and never uploaded**:

- `config/api_keys.json` — your Gemini API key
- `config/certs/` — the dashboard's self-signed TLS key/cert (generated locally)
- `memory/long_term.json` — your stored personal memory
- `*.log` — runtime logs

Only `config/api_keys.example.json` (a placeholder template) is committed, so anyone
cloning the repo knows what to provide without ever seeing your secrets.

---

## 🛠️ Troubleshooting

- **`ModuleNotFoundError: PyQt6`** — install it into your environment: `pip install PyQt6`.
- **SSL / certificate errors on connect** — your machine likely has a TLS-inspecting
  proxy or antivirus. Install `truststore` (`pip install truststore`) so Python trusts
  the OS certificate store; see `SETUP.md`.
- **`UnicodeEncodeError` with emoji when output is redirected** — launch with
  `PYTHONUTF8=1` set (the provided `Start-Jarvis.bat` handles this on Windows).
- **It talks but doesn't act** — make sure your microphone is the default input device
  and that you've granted mic permission.

---

## ⚠️ License

This work is licensed **non-commercial only**, under
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), inherited from the
original MARK XLVIII by FatihMakes. You may use, modify, and share it for non-commercial
purposes as long as you keep the attribution above intact. See the credits section for
the original project and creator.
