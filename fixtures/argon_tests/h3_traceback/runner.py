import config


def retry(fn, *args, **kwargs):
    attempts = 3
    last = None
    for _ in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last = e
    raise last


def do_request(url):
    # pretend HTTP layer: only accepts real URLs
    if not url.startswith("http"):
        raise KeyError(url)
    return f"OK {url}"


def run_job(name):
    url = config.get_endpoint(name)
    return retry(do_request, url)
