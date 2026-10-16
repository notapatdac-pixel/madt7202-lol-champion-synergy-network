"""Run the whole pipeline in order. The collectors read their caches, so a re-run spends no API quota.
--skip-collect rebuilds everything from data/ without a key; --refresh is passed to the pro-games collector only
(the Riot collectors resume from their caches and only fetch what is missing)."""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
COLLECT = [["collect.py", "--platform", "sg2", "--target", "6000", "--pool", "1.15", "--workers", "3"],
           ["collect.py", "--platform", "kr", "--target", "5000", "--pool", "1.15", "--workers", "3"],
           ["collect_pro.py"] + (["--refresh"] if "--refresh" in sys.argv else [])]
STEPS = [["analyze.py"], ["robustness.py"], ["figure.py"], ["report.py"]]

if __name__ == "__main__":
    for step in ([] if "--skip-collect" in sys.argv else COLLECT) + STEPS:
        print("==", " ".join(step), flush=True)
        subprocess.run([sys.executable, str(SRC / step[0]), *step[1:]], cwd=SRC, check=True)
