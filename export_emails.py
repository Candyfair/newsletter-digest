#!/usr/bin/env python3
"""
export_emails.py
Connects to Proton Mail Bridge via IMAP and exports all emails
from a target folder to .eml files on disk.
Credentials are loaded from a .env file if not passed as CLI arguments.
"""

import imaplib
import email
import os
import re
import argparse
from dotenv import load_dotenv

# Load .env from the project root
load_dotenv()


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in filenames."""
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    return name[:80]


def export_emails(host, port, username, password, folder, output_dir):
    """Connect to IMAP server and export emails as .eml files."""

    os.makedirs(output_dir, exist_ok=True)

    print(f"Connecting to {host}:{port}...")
    conn = imaplib.IMAP4(host, port)
    conn.login(username, password)

    status, data = conn.select(f'"{folder}"', readonly=True)
    if status != "OK":
        print(f"Error: folder '{folder}' not found.")
        print("Available folders:")
        _, folders = conn.list()
        for f in folders:
            print(" ", f.decode())
        conn.logout()
        return

    _, message_ids = conn.search(None, "ALL")
    ids = message_ids[0].split()
    print(f"{len(ids)} email(s) found in '{folder}'")

    exported = 0
    for msg_id in ids:
        _, msg_data = conn.fetch(msg_id, "(RFC822)")
        raw_email = msg_data[0][1]

        parsed = email.message_from_bytes(raw_email)
        subject = parsed.get("Subject", "no-subject")
        date_str = parsed.get("Date", "")

        try:
            date = email.utils.parsedate_to_datetime(date_str)
            date_prefix = date.strftime("%Y-%m-%d")
        except Exception:
            date_prefix = "0000-00-00"

        filename = f"{date_prefix}_{sanitize_filename(subject)}.eml"
        filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath):
            print(f"  [skip] {filename}")
            continue

        with open(filepath, "wb") as f:
            f.write(raw_email)

        print(f"  [ok] {filename}")
        exported += 1

    conn.logout()
    print(f"\nDone. {exported} new file(s) exported to '{output_dir}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export emails from Proton Mail Bridge to .eml files")

    # Each argument falls back to the .env value if not provided
    parser.add_argument("--host", default=os.getenv("IMAP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("IMAP_PORT", 1143)))
    parser.add_argument("--username", default=os.getenv("PROTON_USERNAME"))
    parser.add_argument("--password", default=os.getenv("PROTON_BRIDGE_PASSWORD"))
    parser.add_argument("--folder", default=os.getenv("PROTON_FOLDER"))
    parser.add_argument("--output-dir", default="./emails")

    args = parser.parse_args()

    # Fail early if required credentials are missing
    missing = [k for k, v in {
        "username": args.username,
        "password": args.password,
        "folder": args.folder,
    }.items() if not v]

    if missing:
        parser.error(f"Missing required value(s): {', '.join(missing)}. Set them in .env or pass as CLI arguments.")

    export_emails(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        folder=args.folder,
        output_dir=args.output_dir,
    )