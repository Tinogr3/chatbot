"""Utilidades de presentación para el frontend (sin llamadas al backend)."""
import re
from urllib.parse import urlparse, parse_qs


def format_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def extract_video_id(url: str):
    if not url:
        return None
    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    try:
        parsed = urlparse(url)
        if "youtube.com" in parsed.netloc:
            query_params = parse_qs(parsed.query)
            if "v" in query_params:
                return query_params["v"][0]
    except Exception:
        pass
    return None


def is_youtube_url(url: str) -> bool:
    if not url:
        return False
    for pattern in [r"youtube\.com", r"youtu\.be"]:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False
