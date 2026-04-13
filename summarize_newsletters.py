"""
summarize_newsletters.py
------------------------
Pipeline: read .eml files from a local folder → extract text → summarize via
Ollama → generate a single HTML page with one card per newsletter.

Usage:
    python summarize_newsletters.py --eml-dir ./emails --output newsletters.html

Dependencies:
    pip install beautifulsoup4 requests
"""

import argparse
import email
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.utils import parsedate_to_datetime, parseaddr
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "mistral:7b")

# Prompts per source language – always output French.
# Using the same language as the content in the instructions significantly
# reduces the risk of mistral:7b translating instead of summarizing.
SUMMARY_PROMPT_FR = """Tu es un assistant qui résume des newsletters en français.

Lis attentivement le contenu ci-dessous et rédige un RÉSUMÉ SYNTHÉTIQUE en français.

Règles strictes :
- Écris UN seul paragraphe de 3 à 5 phrases complètes.
- Synthétise les idées principales : ne recopie pas le texte mot pour mot.
- Sois factuel et concis. N'invente rien qui ne soit pas dans le texte.
- Ne mentionne pas l'auteur, le nom de la newsletter, ni aucune formule d'introduction.
- Chaque phrase doit être complète. Ne t'arrête jamais en milieu de phrase.
- N'utilise ni listes, ni tirets, ni bullet points.
- Réponds uniquement avec le paragraphe de résumé, sans aucun texte avant ou après.

Contenu de la newsletter :
{content}

Résumé :"""

SUMMARY_PROMPT_EN = """You are an assistant that summarizes English newsletters into fluent, native-quality French.

Read the newsletter content below and write a summary following these rules:
- Output language: FRENCH only. Write as a native French speaker would — no anglicisms, no calques, no word-for-word translation.
- Length: ONE paragraph of exactly 3 to 5 complete sentences.
- Content: synthesize the key ideas. Do not copy or paraphrase sentences. Do not invent anything.
- Style: neutral, factual, journalistic. No introductory formula. No mention of the author or newsletter name.
- Format: plain paragraph only. No lists, no bullet points, no dashes. 
- Every sentence must be complete. Never stop mid-sentence.
- Output only the summary paragraph, with no text before or after.

Example of a good summary (for a different article — for style reference only):
"SpaceX prépare son introduction en Bourse pour lever 75 milliards de dollars afin de financer des centres de données spatiaux dédiés à l'IA générative. La société a imposé sa constellation Starlink comme acteur majeur de l'accès internet haut débit. Son rapprochement avec xAI témoigne des ambitions d'Elon Musk dans l'intelligence artificielle, bien que les pertes considérables de la start-up fassent peser un risque financier sur l'ensemble du groupe."

Newsletter content:
{content}

French summary:"""

# French word sample used for language detection (no external library needed)
_FRENCH_MARKERS = {
    "le", "la", "les", "de", "du", "des", "en", "un", "une",
    "est", "sont", "qui", "que", "dans", "sur", "par", "pour",
    "avec", "mais", "ou", "et", "donc", "car", "si",
}


def _detect_language(text: str) -> str:
    """
    Lightweight language detection based on stop-word frequency.
    Returns 'fr' if the text appears to be French, 'en' otherwise.
    No external dependency required.
    """
    # Sample the first 1000 chars to keep it fast
    sample = text[:1000].lower()
    words = re.findall(r"\b[a-zàâäéèêëîïôùûüç]{2,}\b", sample)
    if not words:
        return "en"
    french_ratio = sum(1 for w in words if w in _FRENCH_MARKERS) / len(words)
    return "fr" if french_ratio > 0.08 else "en"

# Minimum number of characters for a text block to be kept (removes nav/footer
# noise and short Substack tracking artefacts)
MIN_BLOCK_LENGTH = 60

# Maximum number of characters sent to Ollama (avoids context overflow)
MAX_CONTENT_CHARS = 8_000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Newsletter:
    """Holds all data extracted from a single .eml file."""
    file_path: Path
    subject:   str = ""
    sender:    str = ""
    date:      Optional[datetime] = None
    raw_text:  str = ""
    summary:   str = ""
    theme:     str = "Non classé"   # populated later (manual or automatic)
    error:     str = ""             # non-empty if processing failed


# ---------------------------------------------------------------------------
# Step 1 – Parse .eml files
# ---------------------------------------------------------------------------

def _clean_raw_text(html: str) -> str:
    """
    Extract meaningful text from an HTML email body.

    Strategy:
      1. Parse with BeautifulSoup.
      2. Remove <style>, <script>, <img> tags entirely.
      3. Collect only semantic content tags (p, h1-h6, li, blockquote).
      4. Strip Substack / Mailgun invisible tracking characters.
      5. Deduplicate consecutive identical blocks (Substack duplicates <li>).
      6. Join blocks and truncate to MAX_CONTENT_CHARS.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content tags
    for tag in soup.find_all(["style", "script", "img"]):
        tag.decompose()

    # Target only semantic content blocks
    content_tags = soup.find_all(
        ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"]
    )

    blocks = []
    seen = set()  # deduplication set
    for tag in content_tags:
        text = tag.get_text(separator=" ", strip=True)

        # Remove invisible Unicode chars used by email clients for tracking
        text = re.sub(
            r"[\u00ad\u034f\u200b\u200c\u200d\u2060\ufeff\u00a0\u202f͏]+",
            "",
            text,
        )
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Skip short/noise blocks and exact duplicates
        if len(text) < MIN_BLOCK_LENGTH or text in seen:
            continue
        seen.add(text)
        blocks.append(text)

    full_text = "\n\n".join(blocks)
    return full_text[:MAX_CONTENT_CHARS]


def parse_eml(file_path: Path) -> Newsletter:
    """
    Parse a single .eml file and return a Newsletter dataclass.
    Falls back to text/plain if text/html is not available.
    """
    newsletter = Newsletter(file_path=file_path)

    try:
        with open(file_path, "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)

        newsletter.subject = msg.get("subject", "(no subject)").strip()
        raw_from = msg.get("from", "")
        # parseaddr returns ("Display Name", "email@address.com")
        # We keep only the display name, falling back to the email address
        display_name, email_addr = parseaddr(raw_from)
        newsletter.sender = display_name.strip() if display_name.strip() else email_addr.strip()

        # Parse date
        raw_date = msg.get("date")
        if raw_date:
            try:
                newsletter.date = parsedate_to_datetime(raw_date)
            except Exception:
                newsletter.date = None

        # Extract body – prefer HTML over plain text
        html_body  = None
        plain_body = None

        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html" and html_body is None:
                html_body = part.get_content()
            elif ct == "text/plain" and plain_body is None:
                plain_body = part.get_content()

        if html_body:
            newsletter.raw_text = _clean_raw_text(html_body)
        elif plain_body:
            # Basic cleanup for plain-text emails
            text = re.sub(r"[ \t]+", " ", plain_body)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            newsletter.raw_text = text[:MAX_CONTENT_CHARS]
        else:
            newsletter.error = "No readable body found in .eml"

    except Exception as exc:
        newsletter.error = str(exc)
        log.error("Failed to parse %s: %s", file_path.name, exc)

    return newsletter


def load_eml_folder(eml_dir: Path) -> list[Newsletter]:
    """Load all .eml files from a directory."""
    eml_files = sorted(eml_dir.glob("*.eml"))
    if not eml_files:
        log.warning("No .eml files found in %s", eml_dir)
        return []

    log.info("Found %d .eml file(s) in %s", len(eml_files), eml_dir)
    newsletters = [parse_eml(f) for f in eml_files]
    return newsletters


# ---------------------------------------------------------------------------
# Step 2 – Summarize via Ollama
# ---------------------------------------------------------------------------

def check_ollama(model: str = OLLAMA_MODEL) -> bool:
    """
    Verify that Ollama is running and that the requested model is available.
    Prints guidance if the model is missing.
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        available_models = [m["name"] for m in resp.json().get("models", [])]
    except requests.RequestException as exc:
        log.error("Cannot reach Ollama at %s: %s", OLLAMA_BASE_URL, exc)
        log.error("Make sure Ollama is running:  ollama serve")
        return False

    if model not in available_models:
        log.error(
            "Model '%s' is not installed. Available: %s",
            model,
            available_models or "(none)",
        )
        log.error("Install it with:  ollama pull %s", model)
        return False

    log.info("Ollama OK – model '%s' is available.", model)
    return True


def summarize(newsletter: Newsletter, model: str = OLLAMA_MODEL) -> None:
    """
    Call Ollama's /api/generate endpoint and store the summary in-place.
    Automatically selects the prompt language based on content detection.
    Modifies the newsletter object directly.
    """
    if not newsletter.raw_text:
        newsletter.error = newsletter.error or "Empty content – skipping summary."
        return

    # Select prompt based on detected content language
    lang = _detect_language(newsletter.raw_text)
    template = SUMMARY_PROMPT_FR if lang == "fr" else SUMMARY_PROMPT_EN
    log.info("Detected language: %s – using %s prompt", lang, lang.upper())

    prompt = template.format(content=newsletter.raw_text)

    payload = {
        "model":  model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,   # very low → factual, avoids hallucinations
            "num_predict": 600,   # ~5 complete sentences in French; no stop token to avoid early cut
        },
    }

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=120,  # local inference can be slow on CPU
        )
        resp.raise_for_status()
        newsletter.summary = resp.json().get("response", "").strip()
    except requests.RequestException as exc:
        newsletter.error = f"Ollama request failed: {exc}"
        log.error("Summarization failed for '%s': %s", newsletter.subject, exc)


# ---------------------------------------------------------------------------
# Step 3 – Assign themes
# ---------------------------------------------------------------------------

def assign_themes(newsletters: list[Newsletter]) -> None:
    """
    Assign a theme to each newsletter.

    Search order: sender → subject → summary (generated by Ollama).
    Searching the summary as fallback catches cases where the subject line
    alone gives no signal (e.g. "Fundamental Attribution Error").

    Edit THEME_RULES to match your actual subscriptions.
    Format:  "Theme label": [keywords searched in sender + subject + summary]
    """
    THEME_RULES: dict[str, list[str]] = {
        "Intelligence artificielle": [
            # EN
            "ai", "llm", "gpt", "openai", "anthropic", "claude",
            "machine learning", "deep learning", "neural", "artificial intelligence",
            "language model", "chatbot", "generative", "mistral", "gemini",
            "agent", "agents", "agi",
            # FR
            "intelligence artificielle", "modèle de langage", "génératif",
            "génération de texte", "réseau de neurones", "apprentissage automatique",
            "slow ai", "ollama",
        ],
        "Développement web & logiciel": [
            "javascript", "react", "frontend", "css", "web dev",
            "nextjs", "typescript", "node", "python", "software", "developer",
            "engineering", "code", "coding", "github", "api", "backend",
            "développeur", "logiciel", "programmation",
        ],
        "Productivité & outils": [
            "productivity", "notion", "obsidian", "pkm", "tools",
            "workflow", "automation", "habit", "system", "focus",
            "productivité", "outils", "méthode",
        ],
        "Startups & tech business": [
            "startup", "venture", "vc", "saas", "product", "growth",
            "funding", "founder", "ipo", "bourse", "wall street",
            "levée de fonds", "valorisation", "oracle", "spacex", "microsoft",
            "google", "meta", "amazon", "apple",
        ],
        "Carrière & développement personnel": [
            "career", "carrière", "skill", "compétence", "learning", "success",
            "luck", "timing", "attribution", "expert", "accidental",
            "freelance", "job", "hiring", "leadership", "management",
        ],
        "Design & UX": [
            "design", "ux", "ui", "figma", "typography", "interface",
            "visual", "branding", "illustration", "photoshop", "procreate",
        ],
    }

    for nl in newsletters:
        # Build haystack: sender + subject + summary (fallback)
        haystack = (nl.sender + " " + nl.subject + " " + nl.summary).lower()
        matched = False
        for theme, keywords in THEME_RULES.items():
            if any(kw in haystack for kw in keywords):
                nl.theme = theme
                matched = True
                break
        if not matched:
            nl.theme = "Autres"

# ---------------------------------------------------------------------------
# Step 4b – Write index.json
# ---------------------------------------------------------------------------

def write_index(newsletters: list[Newsletter], output_path: Path, uid_map: dict) -> None:
    """
    Write a structured JSON index of all newsletters.
    Used by the React frontend to populate SummaryList and handle deletions.
    """
    index = []
    for nl in newsletters:
        filename = nl.file_path.name
        index.append({
            "id":      str(nl.file_path),   # relative path used as stable React key
            "uid":     uid_map.get(filename),# IMAP UID — None if not found in map
            "subject": nl.subject,
            "sender":  nl.sender,
            "date":    nl.date.isoformat() if nl.date else None,
            "summary": nl.summary,
            "theme":   nl.theme,
        })

    index_path = output_path.parent / "index.json"
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("index.json written to %s", index_path)

# ---------------------------------------------------------------------------
# Step 4 – Render HTML
# ---------------------------------------------------------------------------

def _format_date(dt: Optional[datetime]) -> str:
    """Format a datetime as 'DD Month YYYY' in French."""
    if dt is None:
        return "Date inconnue"
    MONTHS_FR = [
        "", "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    return f"{dt.day} {MONTHS_FR[dt.month]} {dt.year}"


def render_html(newsletters: list[Newsletter], output_path: Path) -> None:
    """
    Generate a single-file HTML page.

    Structure:
      Theme
        └── Sender
              └── Cards sorted chronologically
    """
    # Group: theme → sender → [newsletters]
    groups: dict[str, dict[str, list[Newsletter]]] = {}
    for nl in newsletters:
        groups.setdefault(nl.theme, {}).setdefault(nl.sender, []).append(nl)

    # Sort newsletters within each sender by date (oldest first)
    for theme in groups:
        for sender in groups[theme]:
            groups[theme][sender].sort(
                key=lambda n: n.date or datetime.min
            )

    # Sort themes alphabetically; keep "Autres" / "Non classé" last
    def theme_sort_key(t: str) -> tuple:
        return (t in ("Autres", "Non classé"), t)

    sorted_themes = sorted(groups.keys(), key=theme_sort_key)

    # --- Build HTML ---
    cards_html = ""
    for theme in sorted_themes:
        cards_html += f'<section class="theme-section">\n'
        cards_html += f'  <h2 class="theme-title">{theme}</h2>\n'

        for sender, nls in sorted(groups[theme].items()):
            cards_html += f'  <div class="sender-group">\n'
            cards_html += f'    <h3 class="sender-title">{sender}</h3>\n'

            for nl in nls:
                status_class = "card-error" if nl.error and not nl.summary else ""
                summary_html = (
                    f'<p class="card-summary">{nl.summary}</p>'
                    if nl.summary
                    else f'<p class="card-error-msg">{nl.error or "Résumé non disponible."}</p>'
                )
                date_str = _format_date(nl.date)

                cards_html += f"""
    <article class="card {status_class}">
      <div class="card-header">
        <span class="card-subject">{nl.subject}</span>
        <span class="card-date">{date_str}</span>
      </div>
      {summary_html}
    </article>
"""
            cards_html += "  </div>\n"
        cards_html += "</section>\n"

    generated_at = datetime.now().strftime("%d/%m/%Y à %H:%M")
    total_ok = sum(1 for nl in newsletters if nl.summary)

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Newsletters résumées</title>
  <style>
    /* ── Reset & base ─────────────────────────────────────────── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:          #0f1117;
      --surface:     #1a1d27;
      --surface2:    #22263a;
      --border:      #2e3250;
      --accent:      #6c8efb;
      --accent2:     #a78bfa;
      --text:        #e2e8f0;
      --text-muted:  #8892b0;
      --error:       #fc8181;
      --radius:      10px;
      --font:        'Inter', system-ui, sans-serif;
    }}

    body {{
      font-family: var(--font);
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 2rem 1rem;
    }}

    /* ── Layout ───────────────────────────────────────────────── */
    .container {{ max-width: 860px; margin: 0 auto; }}

    header {{
      padding-bottom: 2rem;
      border-bottom: 1px solid var(--border);
      margin-bottom: 2.5rem;
    }}
    header h1 {{
      font-size: 1.75rem;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }}
    header .meta {{
      margin-top: .5rem;
      font-size: .85rem;
      color: var(--text-muted);
    }}

    /* ── Theme sections ───────────────────────────────────────── */
    .theme-section {{ margin-bottom: 3rem; }}
    .theme-title {{
      font-size: 1.1rem;
      font-weight: 700;
      letter-spacing: .05em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 1.25rem;
      padding-bottom: .4rem;
      border-bottom: 2px solid var(--border);
    }}

    /* ── Sender groups ────────────────────────────────────────── */
    .sender-group {{ margin-bottom: 1.75rem; }}
    .sender-title {{
      font-size: .8rem;
      font-weight: 600;
      letter-spacing: .08em;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: .75rem;
    }}

    /* ── Cards ────────────────────────────────────────────────── */
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.1rem 1.25rem;
      margin-bottom: .75rem;
      transition: border-color .2s;
    }}
    .card:hover {{ border-color: var(--accent); }}
    .card-error {{ border-color: var(--error); opacity: .8; }}

    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 1rem;
      margin-bottom: .6rem;
    }}
    .card-subject {{
      font-weight: 600;
      font-size: .95rem;
      color: var(--text);
      flex: 1;
    }}
    .card-date {{
      font-size: .75rem;
      color: var(--text-muted);
      white-space: nowrap;
    }}
    .card-summary {{
      font-size: .88rem;
      line-height: 1.65;
      color: var(--text-muted);
    }}
    .card-error-msg {{
      font-size: .85rem;
      color: var(--error);
      font-style: italic;
    }}

    footer {{
      text-align: center;
      font-size: .75rem;
      color: var(--text-muted);
      margin-top: 3rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--border);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Newsletters résumées</h1>
      <p class="meta">
        {total_ok} résumé(s) sur {len(newsletters)} newsletter(s) &mdash;
        généré le {generated_at}
      </p>
    </header>

    {cards_html}

    <footer>
      Pipeline local · Ollama ({OLLAMA_MODEL}) · Proton Mail exports
    </footer>
  </div>
</body>
</html>
"""

    output_path.write_text(html, encoding="utf-8")
    log.info("HTML page written to %s", output_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize .eml newsletters with a local Ollama model."
    )
    parser.add_argument(
        "--eml-dir",
        type=Path,
        default=Path("./emails"),
        help="Folder containing .eml files (default: ./emails)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./newsletters.html"),
        help="Output HTML file path (default: ./newsletters.html)",
    )
    parser.add_argument(
        "--model",
        default=OLLAMA_MODEL,
        help=f"Ollama model to use (default: {OLLAMA_MODEL})",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip Ollama calls – useful to test extraction only",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + summarize but do not write the HTML file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # ── 1. Load .eml files
    newsletters = load_eml_folder(args.eml_dir)
    if not newsletters:
        sys.exit(1)

    if not args.no_summary:
        if not check_ollama(args.model):
            log.warning("Ollama check failed – summaries will be empty.")
        else:
            progress_path = args.output.parent / "progress.json"

            # Write total immediately so the UI can display it before summarization starts
            progress_path.write_text(
                json.dumps({"current": 0, "total": len(newsletters), "subject": ""}),
                encoding="utf-8",
            )

            for i, nl in enumerate(newsletters, 1):
                log.info("[%d/%d] Summarizing: %s", i, len(newsletters), nl.subject)

                # Write current progress so Flask can expose it via GET /status
                progress_path.write_text(
                    json.dumps({
                        "current": i,
                        "total":   len(newsletters),
                        "subject": nl.subject,
                    }),
                    encoding="utf-8",
                )

                summarize(nl, model=args.model)

            # Clear progress file once done
            progress_path.unlink(missing_ok=True)

    # ── 3. Assign themes
    assign_themes(newsletters)

    # ── 4. Write index.json
    uid_map_path = args.eml_dir / "uid_map.json"
    uid_map = {}
    if uid_map_path.exists():
        try:
            uid_map = json.loads(uid_map_path.read_text(encoding="utf-8"))
        except Exception:
            log.warning("Could not read uid_map.json — UIDs will be missing from index.")
    write_index(newsletters, args.output, uid_map)

    # ── 5. Render HTML
    if not args.dry_run:
        render_html(newsletters, args.output)

    # ── Summary report
    ok  = sum(1 for nl in newsletters if nl.summary)
    err = sum(1 for nl in newsletters if nl.error)
    log.info("Done. %d summarized, %d error(s).", ok, err)



if __name__ == "__main__":
    main()
