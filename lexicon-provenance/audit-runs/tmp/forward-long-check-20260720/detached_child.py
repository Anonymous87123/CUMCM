import time
from pathlib import Path

time.sleep(0.8)
target = Path(__file__).with_name("poison-target.txt")
target.write_text("LATE_POISON\n", encoding="utf-8")
