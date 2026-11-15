"""
Runner script for Drift — SPHEREx Sky Viewer.
Starts the FastAPI backend and launches the frontend in the user's browser.
"""

import sys
import webbrowser
import threading
import time
import uvicorn

def open_browser():
    time.sleep(1.2)
    url = "http://127.0.0.1:8000"
    print(f"\n[SPHEREx Sky Viewer] Opening browser at {url} ...")
    webbrowser.open(url)

if __name__ == "__main__":
    print("=" * 65)
    print("  DRIFT — SPHEREx SKY VIEWER")
    print("  NASA Space Apps Challenge 2026")
    print("=" * 65)
    print("\nIniciando servidor local FastAPI en http://127.0.0.1:8000 ...")
    print("Pulsa Ctrl+C para detener el servidor.\n")
    
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)

