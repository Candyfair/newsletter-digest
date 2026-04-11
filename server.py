# server.py
import subprocess
import threading
from flask import Flask, jsonify, send_file
from flask_cors import CORS
import os

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

def run_pipeline():
    """Run export_emails.py then summarize_newsletters.py sequentially."""
    with state_lock:
        pipeline_state["status"] = "running"
        pipeline_state["error"] = None

    scripts = [
        ["python3", os.path.join(BASE_DIR, "export_emails.py")],
        ["python3", os.path.join(BASE_DIR, "summarize_newsletters.py"),
         "--eml-dir", os.path.join(BASE_DIR, "emails"),
         "--output", DIGEST_PATH],
    ]

    for script in scripts:
        result = subprocess.run(script, cwd=BASE_DIR)
        if result.returncode != 0:
            with state_lock:
                pipeline_state["status"] = "error"
                pipeline_state["error"] = f"Échec : {os.path.basename(script[1])}"
            return

    with state_lock:
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
    """Return current pipeline state."""
    with state_lock:
        return jsonify(pipeline_state.copy())


@app.route("/digest")
def digest():
    """Serve the generated HTML digest."""
    if not os.path.exists(DIGEST_PATH):
        return jsonify({"error": "Digest non disponible"}), 404
    return send_file(DIGEST_PATH)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)