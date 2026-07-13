"""Hard-kill test child. Usage: python kill_child.py <config.yaml> <project-slug>

Builds a full FRIDAY service against the sandbox config, tells her the given
project's status changed, prints MAIN_TURN_DONE the moment the reply finishes
(BEFORE the memory pass), then idles until the parent test hard-kills us —
simulating Task Manager / power loss at the worst window."""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml  # noqa: E402
from core.service import FridayService  # noqa: E402

config = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
project = sys.argv[2]

svc = FridayService(config=config)
done = threading.Event()
svc.attach(on_token=lambda t: None,
           on_tool=lambda n, a: print(f"TOOL {n}", flush=True),
           on_done=lambda i: done.set(),
           on_error=lambda m: (print("ERR", m, flush=True), done.set()),
           on_confirm=lambda c, d: svc.resolve_confirm(c, True),
           on_ping=lambda t: None, on_proactive=lambda: None,
           on_memory=lambda r: None, on_activity=lambda t: None,
           on_labels=lambda: None)

svc.send_message(
    f"The {project.replace('_', ' ')} project is wrapped up for good - "
    f"set its status to archived.")
done.wait(timeout=300)
print("MAIN_TURN_DONE", flush=True)
time.sleep(600)  # parent kills us here
