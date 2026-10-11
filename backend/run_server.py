"""
Automated Server Launcher
Starts the FastAPI application via uvicorn.
"""

import uvicorn

if __name__ == "__main__":
    print("[Launcher] Starting FastAPI server on http://localhost:8000 ...", flush=True)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
