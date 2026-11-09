"""Lanza el backend desacoplado del shell (sobrevive al cierre de la terminal)."""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
LOG = BASE / "logs" / "uvicorn_detached.log"
LOG.parent.mkdir(parents=True, exist_ok=True)

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

fh = LOG.open("ab")
env = dict(__import__("os").environ, APP_PORT="8001")
p = subprocess.Popen(
    [str(BASE / ".venv" / "Scripts" / "python.exe"), "-m", "uvicorn",
     "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
    cwd=str(BASE),
    stdout=fh, stderr=fh, stdin=subprocess.DEVNULL,
    creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
    close_fds=True, env=env,
)
print("PID", p.pid)
