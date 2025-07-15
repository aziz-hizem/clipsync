# clip_sync.py
"""Cross‑platform clipboard sync between two computers.

Usage (Python 3.9+):

On the computer that will act as the *server* (Mac or Windows):
    python clip_sync.py --server 0.0.0.0 8765

On the other computer (client) providing the server's IP address:
    python clip_sync.py --client 192.168.1.23 8765

Both machines will now mirror text snippets copied on either side.

• Only plain text is synced.
• Requires: pyperclip (pip install pyperclip)
"""

import argparse
import socket
import threading
import time
import sys
from typing import Optional

try:
    import pyperclip  # Cross‑platform clipboard helper
except ImportError:
    print("Please `pip install pyperclip` before running this script.")
    sys.exit(1)

BUFFER_SIZE = 64 * 1024  # 64 KB – plenty for clipboard text
CHECK_INTERVAL = 0.25    # seconds between clipboard polls

def send_loop(conn: socket.socket):
    """Continuously watch the local clipboard and send updates."""
    last_text: Optional[str] = None
    while True:
        try:
            current = pyperclip.paste()
        except Exception:
            current = ""
        if current != last_text and current:
            try:
                data = current.encode("utf‑8")
                conn.sendall(len(data).to_bytes(4, "big") + data)
                last_text = current
            except (BrokenPipeError, OSError):
                break
        time.sleep(CHECK_INTERVAL)


def recv_loop(conn: socket.socket):
    """Receive clipboard data from remote and inject locally."""
    while True:
        try:
            header = conn.recv(4)
            if not header:
                break
            length = int.from_bytes(header, "big")
            data = b""
            while len(data) < length:
                chunk = conn.recv(min(BUFFER_SIZE, length - len(data)))
                if not chunk:
                    break
                data += chunk
            text = data.decode("utf‑8")
            if text:
                # Avoid infinite loops by checking current clipboard first
                if pyperclip.paste() != text:
                    pyperclip.copy(text)
        except (BrokenPipeError, OSError):
            break


def run_server(host: str, port: int):
    print(f"[ClipSync] Waiting for connection on {host}:{port} …")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(1)
        conn, addr = s.accept()
        print(f"[ClipSync] Connected to {addr[0]}:{addr[1]}")
        with conn:
            threading.Thread(target=send_loop, args=(conn,), daemon=True).start()
            recv_loop(conn)
    print("[ClipSync] Connection closed.")


def run_client(server_host: str, port: int):
    print(f"[ClipSync] Connecting to {server_host}:{port} …")
    with socket.create_connection((server_host, port)) as conn:
        print("[ClipSync] Connected! Clipboard is now shared.")
        threading.Thread(target=send_loop, args=(conn,), daemon=True).start()
        recv_loop(conn)
    print("[ClipSync] Connection closed.")


def main():
    parser = argparse.ArgumentParser(description="Share clipboard text between two computers over a LAN.")
    sub = parser.add_subparsers(dest="mode", required=True)

    srv = sub.add_parser("server", help="Start in server mode")
    srv.add_argument("host", help="Host/IP to bind, e.g. 0.0.0.0")
    srv.add_argument("port", type=int, help="Port to listen on", nargs="?", default=8765)

    cli = sub.add_parser("client", help="Start in client mode (connect to server)")
    cli.add_argument("host", help="Server host/IP to connect to")
    cli.add_argument("port", type=int, help="Port", nargs="?", default=8765)



    args = parser.parse_args()

    if args.mode == "server":
        run_server(args.host, args.port)
    else:
        run_client(args.host, args.port)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ClipSync] Exiting…")
