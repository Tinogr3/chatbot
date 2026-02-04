"""
MediaProcessor - Procesamiento de contenido multimedia.
Incluye extracción de transcripciones de videos de YouTube.
"""

import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    VideoUnavailable
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def extract_video_id(url: str) -> Optional[str]:
    """
    Extrae el ID del video de una URL de YouTube.
    
    Soporta formatos:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID
    
    Args:
        url: URL del video de YouTube.
    
    Returns:
        ID del video o None si no se puede extraer.
    """
    if not url:
        return None
    
    # Patrones para diferentes formatos de URL de YouTube
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'  # Solo el ID
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # Intentar extraer de query params
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
    languages: List[str] = ['es', 'en']
) -> Tuple[List[Dict], str]:
    """
    Obtiene la transcripción de un video con timestamps.
    Primero intenta obtener la transcripción de YouTube.
    Si no está disponible, genera una usando Whisper.
    
    Args:
        video_id: ID del video de YouTube.
        languages: Lista de idiomas preferidos (en orden de prioridad).
    
    Returns:
        Tupla con (lista de segmentos con timestamps, idioma de la transcripción).
    """
    # Primero intentar obtener transcripción existente de YouTube
    try:
        # Intentar obtener transcripción en los idiomas preferidos
        for lang in languages:
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                if transcript:
                    return transcript, lang
            except Exception:
                continue
        
        # Intentar sin especificar idioma
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            if transcript:
                return transcript, "auto"
        except Exception:
            pass
            
    except Exception:
        pass
    
    # Si no hay transcripción disponible, generar con Whisper
    print(f"[MediaProcessor] No hay transcripción disponible para {video_id}, generando con Whisper...")
    return generate_transcript_with_whisper(video_id)


def generate_transcript_with_whisper(video_id: str) -> Tuple[List[Dict], str]:
    """
    Genera una transcripción usando Whisper después de descargar el audio con yt-dlp.
    
    Args:
        video_id: ID del video de YouTube.
    
    Returns:
        Tupla con (lista de segmentos con timestamps, idioma detectado).
    """
    import tempfile
    import os
    
    try:
        import yt_dlp
    except ImportError:
        raise ValueError("Se requiere yt-dlp para generar transcripciones. Instala con: pip install yt-dlp")
    
    try:
        import whisper
    except ImportError:
        raise ValueError("Se requiere openai-whisper para generar transcripciones. Instala con: pip install openai-whisper")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Descargar audio del video SIN conversión (no requiere ffmpeg)
        # Preferimos formatos que Whisper puede procesar directamente
        ydl_opts = {
            'format': 'worstaudio',  # Audio de menor calidad = descarga más rápida
            'outtmpl': os.path.join(temp_dir, f"{video_id}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'extract_audio': False,  # No extraer audio (evita ffmpeg)
            'postprocessors': [],  # Sin postprocesadores
        }
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Buscar el archivo descargado (puede tener varias extensiones)
        audio_path = None
        for f in os.listdir(temp_dir):
            if f.startswith(video_id):
                audio_path = os.path.join(temp_dir, f)
                break
        
        if audio_path is None or not os.path.exists(audio_path):
            raise ValueError("No se pudo descargar el audio del video.")
        
        # Transcribir con Whisper
        print(f"[MediaProcessor] Transcribiendo audio con Whisper...")
        model = whisper.load_model("base")  # Modelo base es más rápido
        result = model.transcribe(audio_path)
        
        # Convertir resultado de Whisper a formato compatible
        segments = []
        for segment in result.get("segments", []):
            segments.append({
                "text": segment["text"],
                "start": segment["start"],
                "duration": segment["end"] - segment["start"]
            })
        
        detected_language = result.get("language", "auto")
        
        return segments, detected_language
        
    finally:
        # Limpiar archivos temporales
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def process_video(
    url: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    languages: List[str] = ['es', 'en']
) -> List[Document]:
    """
    Procesa un video de YouTube y retorna documentos con la transcripción dividida en chunks.
    
    Args:
        url: URL del video de YouTube.
        chunk_size: Tamaño máximo de cada chunk en caracteres.
        chunk_overlap: Solapamiento entre chunks.
        languages: Lista de idiomas preferidos para la transcripción.
    
    Returns:
        Lista de Documents de LangChain con metadatos incluyendo timestamps.
    """
    # Extraer ID del video
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"No se pudo extraer el ID del video de la URL: {url}")
    
    # Obtener transcripción con timestamps
    transcript_segments, language = get_transcript_with_timestamps(video_id, languages)
    
    if not transcript_segments:
        raise ValueError("No se encontró transcripción para este video.")
    
    # Crear documentos preservando timestamps
    documents = []
    
    # Estrategia: agrupar segmentos en chunks respetando el tamaño máximo
    current_text = ""
    current_start_time = 0
    segment_texts = []
    
    for segment in transcript_segments:
        segment_text = segment['text'].strip()
        segment_start = segment['start']
        
        # Si es el primer segmento del chunk actual
        if not current_text:
            current_start_time = segment_start
        
        # Verificar si agregar este segmento excede el límite
        potential_text = current_text + " " + segment_text if current_text else segment_text
        
        if len(potential_text) > chunk_size and current_text:
            # Guardar chunk actual
            doc = Document(
                page_content=current_text.strip(),
                metadata={
                    'source': url,
                    'video_id': video_id,
                    'type': 'video',
                    'timestamp': current_start_time,
                    'language': language
                }
            )
            documents.append(doc)
            
            # Empezar nuevo chunk
            current_text = segment_text
            current_start_time = segment_start
        else:
            current_text = potential_text
    
    # Guardar último chunk si hay contenido
    if current_text.strip():
        doc = Document(
            page_content=current_text.strip(),
            metadata={
                'source': url,
                'video_id': video_id,
                'type': 'video',
                'timestamp': current_start_time,
                'language': language
            }
        )
        documents.append(doc)
    
    return documents


def format_timestamp(seconds: float) -> str:
    """
    Formatea segundos a formato HH:MM:SS o MM:SS.
    
    Args:
        seconds: Tiempo en segundos.
    
    Returns:
        String formateado del tiempo.
    """
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def get_youtube_embed_url(video_id: str, start_time: float = 0) -> str:
    """
    Genera la URL de embed de YouTube con timestamp.
    
    Args:
        video_id: ID del video de YouTube.
        start_time: Tiempo de inicio en segundos.
    
    Returns:
        URL de embed para usar en st.video o iframe.
    """
    start_seconds = int(start_time)
    return f"https://www.youtube.com/watch?v={video_id}&t={start_seconds}s"


def is_youtube_url(url: str) -> bool:
    """
    Verifica si una URL es de YouTube.
    
    Args:
        url: URL a verificar.
    
    Returns:
        True si es una URL de YouTube válida.
    """
    if not url:
        return False
    
    youtube_patterns = [
        r'youtube\.com',
        r'youtu\.be'
    ]
    
    for pattern in youtube_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    
    return False
