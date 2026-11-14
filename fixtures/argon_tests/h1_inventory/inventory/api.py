from .service import paginate, total_cents


def handle(path, items):
    # path like "/items?page=2&per=3"
    parts = path.split("?")[1].split("&") if "?" in path else []
    q = dict(p.split("=") for p in parts)
    page = int(q.get("page", "1"))
    per = int(q.get("per", "10"))
    page_items = paginate(items, page, per)
    body = "\n".join(it.label() for it in page_items)
    # PINNED: legacy parser consumes exactly these dict keys
    return {"body": body, "count": len(page_items), "total_cents": total_cents(items)}
