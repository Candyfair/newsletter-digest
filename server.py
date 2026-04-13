import subprocess
import threading
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
import os
import json
from pathlib import Path
import logging
import imaplib
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- Pipeline state ---
pipeline_state = {
    "status": "idle",  # idle | running | done | error
    "error": None,
}
state_lock = threading.Lock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIGEST_PATH = os.path.join(BASE_DIR, "output", "index.html")

# Ensure output directory exists
os.makedirs(os.path.join(BASE_DIR, "output"), exist_ok=True)

current_process = {"proc": None}

def run_pipeline():
    """Run export_emails.py then summarize_newsletters.py sequentially."""
    with state_lock:
        pipeline_state["status"] = "running"
        pipeline_state["error"]  = None

    # Clear stale progress file from previous run immediately
    progress_path = Path(BASE_DIR) / "output" / "progress.json"
    progress_path.unlink(missing_ok=True)

    scripts = [
        ["python3", os.path.join(BASE_DIR, "export_emails.py")],
        ["python3", os.path.join(BASE_DIR, "summarize_newsletters.py"),
         "--eml-dir", os.path.join(BASE_DIR, "emails"),
         "--output",  DIGEST_PATH],
    ]

    for script in scripts:
        proc = subprocess.Popen(script, cwd=BASE_DIR)
        current_process["proc"] = proc
        proc.wait()  # blocks until script finishes or is killed
        current_process["proc"] = None

        if proc.returncode not in (0, -9, -15):  # -9/-15 = killed signals
            with state_lock:
                pipeline_state["status"] = "error"
                pipeline_state["error"]  = f"Échec : {os.path.basename(script[1])}"
            return

    with state_lock:
        # Only mark done if not already cancelled
        if pipeline_state["status"] == "running":
            pipeline_state["status"] = "done"


@app.route("/health")
def health():
    """Basic health check."""
    return jsonify({"status": "ok"})


@app.route("/run", methods=["POST"])
def run():
    """Trigger the pipeline. Rejects if already running."""
    with state_lock:
        if pipeline_state["status"] == "running":
            return jsonify({"error": "Pipeline déjà en cours"}), 409

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
    return jsonify({"status": "running"}), 202


@app.route("/status")
def status():
    # Read progress file written by summarize_newsletters.py if it exists
    progress_path  = Path(BASE_DIR) / "output" / "progress.json"
    progress_str   = None
    progress_total = None

    if pipeline_state["status"] == "running" and progress_path.exists():
        try:
            data    = json.loads(progress_path.read_text(encoding="utf-8"))
            current = data.get("current", 0)
            total   = data.get("total", 0)
            subject = data.get("subject", "")
            # Expose total immediately even before first summary
            progress_total = total
            progress_str = f"[{current}/{total}] {subject}" if current > 0 else None
        except Exception:
            pass

    return jsonify({
        "status":   pipeline_state["status"],
        "error":    pipeline_state.get("error"),
        "progress": progress_str,
        "total":    progress_total,
    })

@app.route("/cancel", methods=["POST"])
def cancel():
    """Kill the running pipeline thread immediately."""
    with state_lock:
        if pipeline_state["status"] != "running":
            return jsonify({"error": "Aucun pipeline en cours"}), 409

    # subprocess.run is blocking — we track the process to kill it
    if current_process["proc"] is not None:
        current_process["proc"].kill()
        current_process["proc"] = None
        print("Pipeline cancelled by user.")

    # Clean up progress file
    progress_path = Path(BASE_DIR) / "output" / "progress.json"
    progress_path.unlink(missing_ok=True)

    with state_lock:
        pipeline_state["status"] = "idle"
        pipeline_state["error"]  = None

    return jsonify({"status": "idle"})


@app.route("/index")
def index_json():
    """Serve the generated index.json for the React frontend."""
    index_path = os.path.join(BASE_DIR, "output", "index.json")
    if not os.path.exists(index_path):
        return jsonify({"error": "index.json non disponible"}), 404
    return send_file(index_path, mimetype="application/json")


@app.route("/digest")
def digest():
    """Serve the generated HTML digest."""
    if not os.path.exists(DIGEST_PATH):
        return jsonify({"error": "Digest non disponible"}), 404
    return send_file(DIGEST_PATH)


@app.route("/email", methods=["DELETE"])
def delete_email():
    """
    Delete selected newsletters:
    1. Remove local .eml files
    2. Move messages to Trash on Proton Mail via IMAP
    3. Update index.json and uid_map.json
    """
    data = request.get_json()
    if not data or "ids" not in data or "uids" not in data:
        return jsonify({"error": "Missing ids or uids"}), 400

    ids  = data["ids"]   # list of relative .eml file paths
    uids = data["uids"]  # list of IMAP UIDs (integers)

    # ── 1. Delete local .eml files
    deleted_files = []
    for eml_id in ids:
        eml_path = Path(BASE_DIR) / eml_id
        if eml_path.exists():
            eml_path.unlink()
            deleted_files.append(eml_path.name)
            log.info("Deleted local file: %s", eml_path.name)

    # ── 2. Move messages to Trash via IMAP
    imap_errors = []
    if uids:
        try:
            conn = imaplib.IMAP4(
                os.getenv("IMAP_HOST", "127.0.0.1"),
                int(os.getenv("IMAP_PORT", 1143)),
            )
            conn.login(
                os.getenv("PROTON_USERNAME"),
                os.getenv("PROTON_BRIDGE_PASSWORD"),
            )

            folder = os.getenv("PROTON_FOLDER")
            status, _ = conn.select(f'"{folder}"')
            if status != "OK":
                raise Exception(f"Cannot select folder: {folder}")

            # Check if server supports MOVE command
            capabilities = conn.capability()[1][0].decode().upper()
            supports_move = "MOVE" in capabilities

            # Build comma-separated UID list for IMAP command
            uid_set = ",".join(str(u) for u in uids)

            if supports_move:
                # Atomic move — preferred
                conn.uid("move", uid_set, "Trash")
                log.info("Moved UIDs %s to Trash (MOVE)", uid_set)
            else:
                # Fallback: copy to Trash, mark as deleted, expunge
                conn.uid("copy", uid_set, "Trash")
                conn.uid("store", uid_set, "+FLAGS", "\\Deleted")
                conn.expunge()
                log.info("Moved UIDs %s to Trash (COPY+EXPUNGE)", uid_set)

            conn.logout()

        except Exception as exc:
            log.error("IMAP error: %s", exc)
            imap_errors.append(str(exc))

    # ── 3. Update index.json
    index_path = Path(BASE_DIR) / "output" / "index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index = [nl for nl in index if nl["id"] not in ids]
            index_path.write_text(
                json.dumps(index, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("index.json updated — %d entry/entries removed", len(ids))
        except Exception as exc:
            log.error("Failed to update index.json: %s", exc)

    # ── 4. Update uid_map.json
    uid_map_path = Path(BASE_DIR) / "emails" / "uid_map.json"
    if uid_map_path.exists():
        try:
            uid_map = json.loads(uid_map_path.read_text(encoding="utf-8"))
            deleted_names = {Path(eml_id).name for eml_id in ids}
            uid_map = {k: v for k, v in uid_map.items() if k not in deleted_names}
            uid_map_path.write_text(
                json.dumps(uid_map, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("uid_map.json updated")
        except Exception as exc:
            log.error("Failed to update uid_map.json: %s", exc)

    response = {"deleted": deleted_files}
    if imap_errors:
        response["imap_errors"] = imap_errors

    return jsonify(response), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)