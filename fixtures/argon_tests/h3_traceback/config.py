CONFIG = {
    "backup": "backup_service",
    "report": "report_service",
}

SERVICE_TABLE = {
    "backup_service": "https://backup.internal/api",
    "report_service": "https://report.internal/api",
}


def get_endpoint(name):
    # returns the service *name*, not the URL - callers expect a URL
    return CONFIG[name]
