# 🧙‍♂️ JARVIS — Mark XLVIII (Agent + Spells fork)

A voice-driven desktop assistant for Windows, macOS, and Linux. It listens, speaks,
sees your screen, and acts on your computer in real time using Google's Gemini Live
API — no monthly subscription, your own API key.

This is a **customized fork** that adds an autonomous *Agent Mode*, a *Harry Potter
spellbook* of voice commands, and a quieter startup. See credits below.

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

## ✨ What this fork adds

- **🤖 Agent Mode** — an autonomous, Claude-style worker. Give it a goal ("fix the bug
  in my project", "organize this folder and tell me what you did") and it reads/edits
  files, runs shell commands, checks the results, and keeps iterating until the task is
  done (capped at 18 steps). Runs on the same Gemini key. A destructive-command guard
  refuses recursive/forced deletes, disk formatting, shutdown, and registry wipes.
  JARVIS routes complex, multi-step work to it automatically.

- **🪄 Spellbook** — cast voice spells:
  | Say | Effect |
  |---|---|
  | `Accio <app>` | Open an app |
  | `Avada Kedavra <app>` | Close that app's process (protected system processes are safe) |
  | `Lumos` / `Nox` | Brightness up / down |
  | `Silencio` | Mute |
  | `Sonorus` / `Quietus` | Volume up / down |

- **🔕 Quiet startup** — JARVIS greets you and then waits. It no longer reads news at
  launch; headlines, weather, and briefings come only when you ask.

## 🧰 Inherited capabilities

Real-time voice conversation · screen & webcam vision · open apps and control the OS
(volume, brightness, Wi-Fi, power) · file management · web search · reminders ·
persistent memory · a code helper and project builder · a phone remote-control dashboard.

## 🚀 Quick start

```bash
# 1. Provide your Gemini API key (never committed)
cp config/api_keys.example.json config/api_keys.json
#    then paste your key from https://aistudio.google.com/apikey

# 2. Install
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
pip install PyQt6 truststore

# 3. Run
python main.py                    # or double-click Start-Jarvis.bat on Windows
```

Full details, including the TLS/trust-store note for machines behind an inspecting
proxy, are in [`SETUP.md`](SETUP.md).

## 🔐 What stays private

Your API key, the dashboard's TLS private key, your stored personal memory, and runtime
logs are all git-ignored and never uploaded.

## ⚠️ License

Non-commercial use only, under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/),
inherited from the original project. Please keep the attribution above intact.
