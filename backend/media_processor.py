import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from langchain_core.documents import Document
from youtube_transcript_api import YouTubeTranscriptApi

from exceptions import VideoTranscriptionError


def extract_video_id(url: str) -> Optional[str]:
    if not url:
        return None
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    try:
        parsed = urlparse(url)
        if 'youtube.com' in parsed.netloc:
            query_params = parse_qs(parsed.query)
            if 'v' in query_params:
                return query_params['v'][0]
    except Exception:
        pass
    return None


def get_transcript_with_timestamps(
    video_id: str,
    languages: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    if languages is None:
        languages = ["es", "en"]

    ytt_api = YouTubeTranscriptApi()

    # Intentar cada idioma individualmente
    for lang in languages:
        try:
            fetched = ytt_api.fetch(video_id, languages=[lang])
            raw = fetched.to_raw_data()
            if raw:
                return raw, lang
        except Exception:
            continue

    # Intentar cualquier transcripción disponible (auto-generada o manual)
    try:
        transcript_list = ytt_api.list(video_id)
        for transcript in transcript_list:
            try:
                raw = transcript.fetch().to_raw_data()
                if raw:
                    return raw, transcript.language_code
            except Exception:
                continue
    except Exception:
        pass

    return generate_transcript_with_whisper(video_id)


def generate_transcript_with_whisper(video_id: str) -> Tuple[List[Dict[str, Any]], str]:
    import os
    import tempfile

    try:
        import yt_dlp
    except ImportError as e:
        raise VideoTranscriptionError(
            "Se requiere yt-dlp para generar transcripciones. Instala con: pip install yt-dlp"
        ) from e
    try:
        import whisper
    except ImportError as e:
        raise VideoTranscriptionError(
            "Se requiere openai-whisper para generar transcripciones. Instala con: pip install openai-whisper"
        ) from e
    temp_dir = tempfile.mkdtemp()
    try:
        ydl_opts = {
            'format': 'worstaudio',
            'outtmpl': os.path.join(temp_dir, f"{video_id}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'extract_audio': False,
            'postprocessors': [],
        }
        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        audio_path = None
        for f in os.listdir(temp_dir):
            if f.startswith(video_id):
                audio_path = os.path.join(temp_dir, f)
                break
        if audio_path is None or not os.path.exists(audio_path):
            raise VideoTranscriptionError("No se pudo descargar el audio del video.")
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        segments = [
            {"text": s["text"], "start": s["start"], "duration": s["end"] - s["start"]}
            for s in result.get("segments", [])
        ]
        return segments, result.get("language", "auto")
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def process_video(
    url: str,
    chunk_size: int = 1000,
    languages: Optional[List[str]] = None,
) -> List[Document]:
    if languages is None:
        languages = ["es", "en"]
    video_id = extract_video_id(url)
    if not video_id:
        raise VideoTranscriptionError(f"No se pudo extraer el ID del video de la URL: {url}")
    transcript_segments, language = get_transcript_with_timestamps(video_id, languages)
    if not transcript_segments:
        raise VideoTranscriptionError("No se encontró transcripción para este video.")
    documents = []
    current_text = ""
    current_start_time = 0
    for segment in transcript_segments:
        segment_text = segment['text'].strip()
        segment_start = segment['start']
        if not current_text:
            current_start_time = segment_start
        potential_text = current_text + " " + segment_text if current_text else segment_text
        if len(potential_text) > chunk_size and current_text:
            documents.append(Document(
                page_content=current_text.strip(),
                metadata={'source': url, 'video_id': video_id, 'type': 'video', 'timestamp': current_start_time, 'language': language}
            ))
            current_text = segment_text
            current_start_time = segment_start
        else:
            current_text = potential_text
    if current_text.strip():
        documents.append(Document(
            page_content=current_text.strip(),
            metadata={'source': url, 'video_id': video_id, 'type': 'video', 'timestamp': current_start_time, 'language': language}
        ))
    return documents


def get_video_title(video_id: str) -> Optional[str]:
    """Devuelve el título del video sin descargarlo.

    Intenta primero con yt-dlp (extract_info sin descarga). Si no está
    disponible o falla, devuelve None y el caller usará la URL como fallback.
    """
    try:
        import yt_dlp

        url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = (info or {}).get("title")
            return str(title).strip() if title else None
    except Exception:
        return None


def is_youtube_url(url: str) -> bool:
    if not url:
        return False
    for pattern in [r'youtube\.com', r'youtu\.be']:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False
