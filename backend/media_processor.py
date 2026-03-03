"""
MediaProcessor - Procesamiento de contenido multimedia (backend).
"""
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
    try:
        for lang in languages:
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                if transcript:
                    return transcript, lang
            except Exception:
                continue
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            if transcript:
                return transcript, "auto"
        except Exception:
            pass
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
    chunk_overlap: int = 200,
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


def format_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def get_youtube_embed_url(video_id: str, start_time: float = 0) -> str:
    return f"https://www.youtube.com/watch?v={video_id}&t={int(start_time)}s"


def is_youtube_url(url: str) -> bool:
    if not url:
        return False
    for pattern in [r'youtube\.com', r'youtu\.be']:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False
