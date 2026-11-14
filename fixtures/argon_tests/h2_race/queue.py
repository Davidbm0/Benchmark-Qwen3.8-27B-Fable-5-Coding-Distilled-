import threading
import time


class JobQueue:
    """Simple in-process job queue used by the nightly batch runner."""

    def __init__(self):
        self._jobs = []
        self._processed = []
        self._idx = 0

    def add(self, job_id):
        self._jobs.append(job_id)

    def _worker(self):
        while True:
            # check-then-act on the shared index (no lock)
            i = self._idx
            if i >= len(self._jobs):
                return
            # simulate a tiny scheduling delay (real code does I/O here)
            time.sleep(0.001)
            job = self._jobs[i]
            self._idx = i + 1
            self._processed.append(job)

    def run(self, workers=8):
        threads = [threading.Thread(target=self._worker) for _ in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return self._processed
