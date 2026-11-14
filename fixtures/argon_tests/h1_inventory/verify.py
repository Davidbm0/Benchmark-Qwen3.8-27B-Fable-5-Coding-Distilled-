import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from inventory.models import Item
from inventory.service import paginate, total_cents
from inventory.api import handle

items = [Item(f"n{i}", 10 + i) for i in range(7)]
fails = []

# 1. pagination: page is 1-based, page 1 must return the FIRST per_page items
p1 = [i.name for i in paginate(items, 1, 3)]
if p1 != ["n0", "n1", "n2"]:
    fails.append(f"paginate(items,1,3) -> {p1}, expected ['n0','n1','n2']")

# 2. tag isolation between instances
a = Item("a", 1.0)
b = Item("b", 1.0)
a.tags.append("x")
if b.tags != []:
    fails.append(f"tag leak: b.tags={b.tags}")

# 3. money: 3 x 1.00 with 15% discount must be 255 cents (half-to-even cent rule)
got = total_cents([Item("w", 1.00) for _ in range(3)], 15)
if got != 255:
    fails.append(f"total_cents(3x1.00, 15%) -> {got}, expected 255")

# 4. pinned API contract (legacy parser)
r = handle("/items?page=1&per=3", items)
if set(r.keys()) != {"body", "count", "total_cents"}:
    fails.append(f"handle keys changed: {set(r.keys())}")
if r.get("count") != 3:
    fails.append(f"handle count -> {r.get('count')}, expected 3")

if fails:
    print("CI FAIL:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("TEST PASS")
