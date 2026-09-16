"""
Automated Server Launcher
Ensures MongoDB is running locally before starting the FastAPI application.
"""

import os
import sys
import time
import socket
import subprocess
import uvicorn

MONGOD_PATH = r"C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe"
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "mongodb_data"))
LOG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "mongod.log"))


def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def ensure_mongodb():
    if is_port_open("127.0.0.1", 27017):
        print("[Launcher] MongoDB is already active and listening on port 27017.", flush=True)
        return

    print("[Launcher] Starting local MongoDB instance...", flush=True)
    os.makedirs(DB_PATH, exist_ok=True)

    if os.path.exists(MONGOD_PATH):
        cmd = [MONGOD_PATH, "--port", "27017", "--dbpath", DB_PATH, "--bind_ip", "127.0.0.1", "--logpath", LOG_PATH, "--logappend"]
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        subprocess.Popen(cmd, creationflags=flags)
        
        # Wait up to 10 seconds for MongoDB to start
        for _ in range(20):
            time.sleep(0.5)
            if is_port_open("127.0.0.1", 27017):
                print("[Launcher] MongoDB successfully started on port 27017.", flush=True)
                return
        print("[Launcher WARNING] MongoDB did not respond on port 27017 within 10s.", flush=True)
    else:
        print(f"[Launcher WARNING] Could not find mongod executable at {MONGOD_PATH}.", flush=True)


if __name__ == "__main__":
    ensure_mongodb()
    print("[Launcher] Starting FastAPI server on http://localhost:8000 ...", flush=True)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
