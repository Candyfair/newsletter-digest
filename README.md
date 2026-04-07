# newsletter-digest

Automated pipeline to export, summarize and browse newsletters via a local LLM.

Reads `.eml` files exported from Proton Mail, summarizes each newsletter in French using a local Ollama model, and generates a browsable dark-mode HTML page organized by theme and sender.

---

## Features

- Export emails from Proton Mail via Bridge (IMAP) to `.eml` files
- Extract clean plain text from HTML emails (Substack, Mailgun, etc.)
- Auto-detect email language (FR/EN) — summaries always output in French
- Summarize via a local Ollama model (no cloud API, no token cost)
- Generate a single dark-mode HTML page: theme → sender → chronological cards
- Keyword-based theme attribution with fallback to summary content
- Fully idempotent export (skips already-downloaded emails)
- CLI interface for both scripts

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally with a pulled model (e.g. `mistral:7b`)
- [Proton Mail Bridge](https://proton.me/mail/bridge) (for email export)

---

## Installation

```bash
git clone https://github.com/your-username/newsletter-digest.git
cd newsletter-digest

pip install beautifulsoup4 requests python-dotenv
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
PROTON_USERNAME=your@proton.me
PROTON_BRIDGE_PASSWORD=your-bridge-password
PROTON_FOLDER=Newsletters
IMAP_HOST=127.0.0.1
IMAP_PORT=1143
```

> `.env` is git-ignored. Never commit it.

---

## Usage

### 1. Export emails from Proton Mail

Make sure Proton Mail Bridge is running, then:

```bash
python3 export_emails.py --output-dir ./emails
```

All emails from the configured folder are saved as `.eml` files in `./emails/`.

| Argument | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | IMAP host (Bridge) |
| `--port` | `1143` | IMAP port (Bridge) |
| `--username` | from `.env` | Proton Mail address |
| `--password` | from `.env` | Bridge IMAP password |
| `--folder` | from `.env` | IMAP folder to export |
| `--output-dir` | `./emails` | Destination for `.eml` files |

### 2. Summarize and generate HTML

Make sure Ollama is running, then:

```bash
python3 summarize_newsletters.py \
  --eml-dir ./emails \
  --output ./output/index.html \
  --model mistral:7b
```

Open `./output/index.html` in your browser to browse your summaries.

| Argument | Default | Description |
|---|---|---|
| `--eml-dir` | required | Folder containing `.eml` files |
| `--output` | required | Output HTML file path |
| `--model` | `mistral:7b` | Ollama model to use |
| `--no-summary` | — | Skip LLM, export structure only |
| `--dry-run` | — | Parse emails without writing output |

---

## Project structure

```
newsletter-digest/
├── .env                  # Local secrets (git-ignored)
├── .env.example          # Credentials template
├── .gitignore
├── export_emails.py      # Step 1: export .eml from Proton Mail Bridge
├── summarize_newsletters.py  # Step 2: summarize and generate HTML
├── emails/               # Downloaded .eml files (git-ignored)
└── output/               # Generated HTML page (git-ignored)
```

---

## Roadmap

- [ ] Flask web interface with a trigger button and live logs
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