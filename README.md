# newsletter-digest

Automated pipeline to export, summarize and browse newsletters via a local LLM.

Reads `.eml` files exported from Proton Mail, summarizes each newsletter in French or English using a local Ollama model, and generates a browsable dark-mode HTML page organized by theme and sender. A React web interface allows triggering the pipeline, monitoring progress in real time, and managing summaries.

---

## Features

- Export emails from Proton Mail via Bridge (IMAP) to `.eml` files
- Extract clean plain text from HTML emails (Substack, Mailgun, etc.)
- Auto-detect email language (FR/EN) — summaries always output in French
- Summarize via a local Ollama model (no cloud API, no token cost)
- Generate a single dark-mode HTML page: theme → sender → chronological cards
- Keyword-based theme attribution with fallback to summary content
- Fully idempotent export (skips already-downloaded emails)
- CLI interface for both Python scripts
- Flask API server to trigger and monitor the pipeline
- React web interface with real-time progress, summary cards, and email deletion
- Push notifications via ntfy.sh and email on pipeline completion

---

## Requirements

- Python 3.9+
- Node.js 18+ (for the web interface)
- [Ollama](https://ollama.com) running locally with a pulled model (e.g. `mistral:7b`)
- [Proton Mail Bridge](https://proton.me/mail/bridge) (for email export)

---

## Installation

```bash
git clone https://github.com/Candyfair/newsletter-digest.git
cd newsletter-digest
```

### Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Web interface dependencies

```bash
cd web
npm install
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
# Proton Mail Bridge — IMAP
PROTON_USERNAME=your@proton.me
PROTON_BRIDGE_PASSWORD=your-bridge-imap-password
PROTON_FOLDER=Newsletters
IMAP_HOST=127.0.0.1
IMAP_PORT=1143

# Proton Mail Bridge — SMTP (for email notifications)
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
SMTP_USERNAME=your@proton.me
SMTP_PASSWORD=your-bridge-smtp-password
NOTIFY_TO=your@proton.me

# Ollama
OLLAMA_HOST=http://localhost:11434

# ntfy.sh (push notifications)
NTFY_TOPIC=your-ntfy-topic
```

> `.env` is git-ignored. Never commit it.

---

## Quick start

Make sure the following are running before starting:

- **Proton Mail Bridge** — for IMAP/SMTP access
- **Ollama** — `ollama serve` with your model pulled (e.g. `ollama pull mistral:7b`)

### 1. Activate the Python virtual environment

```bash
source venv/bin/activate
```

### 2. Start the Flask server

```bash
python server.py
```

Flask runs on `http://localhost:5000`.

### 3. Start the web interface

In a separate terminal:

```bash
cd web
npm run dev
```

Open `http://localhost:5173` in your browser. Click **"Lancer le digest"** to start the pipeline. Progress is displayed in real time. When complete, a link to the generated digest appears.

---

## CLI usage

The pipeline scripts can also be run directly without the web interface.

### Export emails from Proton Mail

```bash
python3 export_emails.py --output-dir ./emails
```

| Argument | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | IMAP host (Bridge) |
| `--port` | `1143` | IMAP port (Bridge) |
| `--username` | from `.env` | Proton Mail address |
| `--password` | from `.env` | Bridge IMAP password |
| `--folder` | from `.env` | IMAP folder to export |
| `--output-dir` | `./emails` | Destination for `.eml` files |

### Summarize and generate HTML

```bash
python3 summarize_newsletters.py \
  --eml-dir ./emails \
  --output ./output/index.html \
  --model mistral:7b
```

| Argument | Default | Description |
|---|---|---|
| `--eml-dir` | required | Folder containing `.eml` files |
| `--output` | required | Output HTML file path |
| `--model` | `mistral:7b` | Ollama model to use |
| `--no-summary` | — | Skip LLM, export structure only |
| `--dry-run` | — | Parse emails without writing output |

---

## Flask API

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Returns `{"status": "ok"}` |
| `POST` | `/run` | Triggers the pipeline (non-blocking, returns `202`) |
| `GET` | `/status` | Returns current pipeline status and progress |
| `POST` | `/cancel` | Cancels a running pipeline |
| `GET` | `/digest` | Serves the generated `output/index.html` |
| `GET` | `/index` | Returns `output/index.json` (summary list) |
| `DELETE` | `/email` | Deletes an email locally and moves it to IMAP Trash |

---

## Project structure

```
newsletter-digest/
├── .env                        # Local secrets (git-ignored)
├── .env.example                # Credentials template
├── .gitignore
├── requirements.txt            # Python dependencies
├── export_emails.py            # Step 1: export .eml from Proton Mail Bridge
├── summarize_newsletters.py    # Step 2: summarize and generate HTML
├── server.py                   # Flask API server
├── web/                        # React web interface (Vite + Tailwind v4)
│   ├── src/
│   │   ├── context/            # Global app context (theme, lang)
│   │   └── ...
│   ├── vite.config.js
│   └── package.json
├── emails/                     # Downloaded .eml files (git-ignored)
└── output/                     # Generated HTML + JSON (git-ignored)
```

---

## Roadmap

- [x] Flask API server (trigger, status, cancel, digest)
- [x] React web interface with real-time progress
- [x] Email deletion from UI (local + IMAP Trash)
- [x] Push notifications (ntfy.sh + email via Proton Bridge SMTP)
- [ ] iOS Shortcut for one-tap pipeline trigger
- [ ] Docker + Docker Compose for home server deployment
- [ ] Migration to Mistral Small 3.1 24B on RTX 3090
- [ ] Tailscale exposure for remote access

---

## Models

| Environment | Model | Hardware |
|---|---|---|
| Development | `mistral:7b` | Mac Mini M4, 16 GB RAM |
| Production | `mistral-small:24b` | RTX 3090 24 GB VRAM |

Any Ollama-compatible model can be used via the `--model` argument.

---

## License

MIT