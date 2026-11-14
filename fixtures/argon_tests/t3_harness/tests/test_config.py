import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# --- homegrown "fixture": chdir to a temp dir AND mock Path with basename-only resolution ---
_tmp = Path(__file__).parent / "_tmp_chdir"
_tmp.mkdir(exist_ok=True)
os.chdir(_tmp)

_RealPath = Path
class _MockPath:
    def __init__(self, *parts):
        # BUG: resolves relative to CWD (now _tmp_chdir), not relative to the source file
        self._p = _RealPath(*[os.path.basename(str(x)) for x in parts])
    def __truediv__(self, other):
        self._p = self._p / os.path.basename(str(other))
        return self
    def read_text(self):
        return self._p.read_text()

import config as _cfg_mod
_cfg_mod.Path = _MockPath

import config

def test_parse_config():
    cfg = config.parse_config()
    assert cfg["retry"] == "3"
    assert cfg["timeout_ms"] == "250"
    assert cfg["region"] == "cluj"

if __name__ == "__main__":
    test_parse_config()
    print("TEST PASS")
