import os
from pathlib import Path

DEFAULTS_FILE = "defaults.ini"

def parse_config():
    # loads defaults relative to THIS source file - correct by design
    path = Path(__file__).parent / DEFAULTS_FILE
    cfg = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k, _, v = line.partition("=")
        cfg[k.strip()] = v.strip()
    return cfg
