import subprocess
import threading
from flask import Flask, jsonify, send_file
from flask_cors import CORS
import os
import json
from pathlib import Path
import logging

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)