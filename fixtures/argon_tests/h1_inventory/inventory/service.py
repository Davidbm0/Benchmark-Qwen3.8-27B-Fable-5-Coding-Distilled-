def paginate(items, page, per_page):
    """page is 1-based."""
    start = page * per_page
    return items[start:start + per_page]


def total_cents(items, discount_pct=0):
    total = 0.0
    for it in items:
        total += it.price
    total = total * (100 - discount_pct) / 100
    return int(total * 100)
