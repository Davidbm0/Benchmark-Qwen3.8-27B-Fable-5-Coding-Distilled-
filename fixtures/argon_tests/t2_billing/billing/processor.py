def format_invoice_line(item_name, qty, unit_price, discount_pct=0):
    # LEGACY FORMAT - DO NOT CHANGE RETURN TYPE OR DICT KEYS
    # Downstream C++ parser expects exact keys: "raw_label", "net_cents", "flags"
    subtotal = qty * unit_price
    discount = subtotal * (discount_pct / 100.0)
    net = round(subtotal - discount, 2)
    net_cents = int(net * 100)
    flags = "DISC" if discount_pct else "STD"
    return {
        "raw_label": f"{item_name.upper():<20}|QTY:{qty:03d}",
        "net_cents": net_cents,
        "flags": flags
    }
