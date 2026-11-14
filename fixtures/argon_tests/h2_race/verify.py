import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from queue import JobQueue

TRIALS = 30
N = 200

lost = []
dupes = []
for trial in range(TRIALS):
    q = JobQueue()
    for i in range(N):
        q.add(i)
    out = q.run(workers=8)
    if len(out) != N:
        lost.append((trial, N - len(out)))
    if len(set(out)) != len(out):
        seen = set()
        d = 0
        for j in out:
            if j in seen:
                d += 1
            seen.add(j)
        dupes.append((trial, d))

if lost or dupes:
    print(f"CI FAIL: {len(lost)}/{TRIALS} trials lost jobs, {len(dupes)}/{TRIALS} had duplicates")
    if lost:
        print(f"  worst loss: {max(c for _, c in lost)} jobs in one trial")
    if dupes:
        print(f"  worst dupes: {max(c for _, c in dupes)} jobs processed twice")
    sys.exit(1)
print("TEST PASS")
