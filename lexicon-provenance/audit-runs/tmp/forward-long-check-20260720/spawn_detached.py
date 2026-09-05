import os
import subprocess
import sys

child = os.path.join(os.path.dirname(__file__), "detached_child.py")
kwargs = {}
if os.name == "nt":
    kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
else:
    kwargs["start_new_session"] = True
subprocess.Popen(
    [sys.executable, child],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    close_fds=True,
    **kwargs,
)
