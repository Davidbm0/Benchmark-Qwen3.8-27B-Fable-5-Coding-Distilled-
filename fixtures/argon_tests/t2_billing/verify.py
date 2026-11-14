import ast

# --- verify T2: billing fix (fixture cu caz real de esec: 3 x 1.00, disc 15% -> 255, naive da 254) ---
src = open("billing/processor.py").read()

# 1. signature + defaults must be preserved
tree = ast.parse(src)
fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "format_invoice_line")
args = [a.arg for a in fn.args.args]
assert args == ["item_name", "qty", "unit_price", "discount_pct"], f"signature changed: {args}"
defaults = [ast.unparse(d) for d in fn.args.defaults]
assert defaults == ["0"], f"defaults changed: {defaults}"

# 2. return type + pinned dict keys
exec(compile(src, "billing/processor.py", "exec"), globals())
r = format_invoice_line("Widget", 3, 1.00, discount_pct=15)
assert isinstance(r, dict), "return type changed"
assert set(r.keys()) == {"raw_label", "net_cents", "flags"}, f"keys changed: {set(r.keys())}"

# 3. the failing case (banker's rounding la nivel de cent)
assert r["net_cents"] == 255, f"net_cents wrong: {r['net_cents']}"
assert r["raw_label"] == "WIDGET              |QTY:003", f"raw_label changed: {r['raw_label']!r}"
assert r["flags"] == "DISC"

# 4. extra probes — half-even la .125/.135 + cazul initial din enunt
r0 = format_invoice_line("Widget", 3, 19.99, discount_pct=15)
assert r0["net_cents"] == 5097, f"probe0: {r0['net_cents']}"
r2 = format_invoice_line("Sprocket", 7, 3.33, discount_pct=10)
assert r2["net_cents"] == 2098, f"probe2: {r2['net_cents']}"
r3 = format_invoice_line("Bolt", 1, 0.125, discount_pct=0)
assert r3["net_cents"] == 12, f"probe3 (half-even 0.125->0.12): {r3['net_cents']}"
r4 = format_invoice_line("Nut", 1, 0.135, discount_pct=0)
assert r4["net_cents"] == 14, f"probe4 (half-even 0.135->0.14): {r4['net_cents']}"
r5 = format_invoice_line("Plain", 1, 1.14, discount_pct=0)
assert r5["net_cents"] == 114, f"probe5 (1.14 float trap): {r5['net_cents']}"

print("TEST PASS")
