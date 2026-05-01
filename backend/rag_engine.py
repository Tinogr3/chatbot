"""
Motor RAG (backend) - Sin dependencias de Streamlit.
"""
import asyncio
import base64
import functools
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from pdfminer.pdfparser import PDFSyntaxError
except ImportError:
    PDFSyntaxError = None  # type: ignore[misc, assignment]

try:
    from google.auth.exceptions import GoogleAuthError
except ImportError:
    GoogleAuthError = None  # type: ignore[misc, assignment]

try:
    from google.api_core.exceptions import GoogleAPICallError
except ImportError:
    GoogleAPICallError = None  # type: ignore[misc, assignment]

from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools.retriever import create_retriever_tool
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from config import get_credentials_and_project
from exceptions import DocumentProcessingError
from gemini_models import gemini_flash_model_id, gemini_pro_model_id
from logger import get_logger
from user_memory import UserMemoryManager

logger = get_logger("rag_engine")

_embeddings_cache: Optional[GoogleGenerativeAIEmbeddings] = None

# Pool opcional registrado por FastAPI (lifespan); si es None, run_in_executor usa el executor por defecto del loop.
_rag_thread_pool: Optional[ThreadPoolExecutor] = None

# Excepciones de carga/parseo PDF (PyPDF/pdfminer) para logging explícito sin except Exception genérico.
_PDF_LOAD_ERRORS: Tuple[type, ...] = (OSError, FileNotFoundError, ValueError, MemoryError)
if PDFSyntaxError is not None:
    _PDF_LOAD_ERRORS = _PDF_LOAD_ERRORS + (PDFSyntaxError,)

# Fallos típicos de embeddings (Vertex / API key / cliente Google).
_EMBEDDINGS_INIT_ERRORS: Tuple[type, ...] = (OSError, ValueError, TypeError, RuntimeError)
if GoogleAuthError is not None:
    _EMBEDDINGS_INIT_ERRORS = _EMBEDDINGS_INIT_ERRORS + (GoogleAuthError,)

# Chroma / persistencia / lotes de documentos.
_VECTOR_STORE_ERRORS: Tuple[type, ...] = (OSError, RuntimeError, ValueError, TypeError)

# Descripción de imagen vía Gemini (hilos paralelos en procesar_pdf).
_IMAGE_TASK_ERRORS: Tuple[type, ...] = (OSError, RuntimeError, ValueError, TimeoutError)
if GoogleAPICallError is not None:
    _IMAGE_TASK_ERRORS = _IMAGE_TASK_ERRORS + (GoogleAPICallError,)


def set_rag_thread_pool(executor: Optional[ThreadPoolExecutor]) -> None:
    """Registra el ThreadPoolExecutor del lifespan de FastAPI para tareas RAG intensivas."""
    global _rag_thread_pool
    _rag_thread_pool = executor


async def _run_in_rag_pool(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Ejecuta trabajo bloqueante en el pool RAG (o el executor por defecto del event loop)."""
    loop = asyncio.get_running_loop()
    if kwargs:
        return await loop.run_in_executor(_rag_thread_pool, functools.partial(fn, *args, **kwargs))
    return await loop.run_in_executor(_rag_thread_pool, fn, *args)


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _bounded_env_int(name: str, default: int, low: int, high: int) -> int:
    """Entero de entorno acotado a ``[low, high]`` (útil para paralelismo sin disparar RAM/API)."""
    v = _env_int(name, default)
    return max(low, min(high, v))


def extract_text(content: Any) -> str:
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
            elif isinstance(item, str):
                text_parts.append(item)
        return "".join(text_parts)
    return str(content) if content is not None else ""


def get_gemini_vision_model(max_tokens: int = 65535) -> Optional[ChatGoogleGenerativeAI]:
    try:
        vision_model = gemini_flash_model_id()
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            return ChatGoogleGenerativeAI(
                model=vision_model,
                google_api_key=api_key,
                temperature=1,
                max_output_tokens=max_tokens
            )
        credentials, project_id = get_credentials_and_project()
        if credentials and project_id:
            return ChatGoogleGenerativeAI(
                model=vision_model,
                credentials=credentials,
                project=project_id,
                location="global",
                temperature=1,
                max_output_tokens=max_tokens
            )
    except Exception as e:
        logger.warning("Error initializing vision model: %s", e)
    return None


def describe_image_with_gemini(image_bytes: bytes, context: str = "", max_tokens: int = 65535) -> str:
    model = get_gemini_vision_model(max_tokens=max_tokens)
    if not model:
        return ""
    try:
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        prompt = f"""Analiza esta imagen de un documento educativo y proporciona una descripción detallada y útil para el aprendizaje.
Incluye: tipo de contenido visual, descripción del contenido principal, datos o texto visible relevante.
{f'Contexto del documento: {context}' if context else ''}
Responde en español con una descripción clara y concisa."""
        message = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
        ])
        response = model.invoke([message])
        return extract_text(response.content).strip()
    except Exception as e:
        logger.warning("Error describing image: %s", e)
        return ""


def extract_images_from_pdf(pdf_path: str) -> List[Tuple[bytes, int, str]]:
    """Extrae imágenes de un PDF; retorna lista de (bytes, número_página, id_imagen)."""
    images = []
    try:
        import fitz
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):
            for img_index, img in enumerate(page.get_images()):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    if len(image_bytes) > 5000:
                        images.append((image_bytes, page_num + 1, f"page{page_num + 1}_img{img_index + 1}"))
                except (OSError, ValueError, KeyError, RuntimeError) as img_err:
                    logger.debug(
                        "Extracción imagen PDF omitida (página %s, img %s): %s",
                        page_num + 1,
                        img_index,
                        img_err,
                    )
                    continue
        doc.close()
    except ImportError:
        try:
            from unstructured.partition.pdf import partition_pdf
            with tempfile.TemporaryDirectory() as temp_dir:
                elements = partition_pdf(
                    filename=pdf_path,
                    extract_images_in_pdf=True,
                    extract_image_block_output_dir=temp_dir,
                    strategy="hi_res"
                )
                import glob
                for img_path in glob.glob(os.path.join(temp_dir, "*.png")) + glob.glob(os.path.join(temp_dir, "*.jpg")):
                    with open(img_path, "rb") as f:
                        image_bytes = f.read()
                    if len(image_bytes) > 5000:
                        images.append((image_bytes, 1, Path(img_path).stem))
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(
                "Extracción imágenes PDF (unstructured): %s: %s",
                type(e).__name__,
                e,
                exc_info=True,
            )
    except (OSError, RuntimeError, ValueError) as e:
        logger.warning(
            "Extracción imágenes PDF (PyMuPDF): %s: %s",
            type(e).__name__,
            e,
            exc_info=True,
        )
    return images


def get_embeddings() -> Optional[GoogleGenerativeAIEmbeddings]:
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache
    try:
        credentials, project_id = get_credentials_and_project()
        if not project_id:
            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                _embeddings_cache = GoogleGenerativeAIEmbeddings(model="text-embedding-004", api_key=api_key)
                return _embeddings_cache
            return None
        _embeddings_cache = GoogleGenerativeAIEmbeddings(
            model="text-embedding-004",
            vertexai=True,
            project=project_id,
            location="global",
        )
        return _embeddings_cache
    except _EMBEDDINGS_INIT_ERRORS as e:
        logger.warning(
            "Embeddings Google (text-embedding-004): fallo de credenciales, proyecto o cliente — %s: %s",
            type(e).__name__,
            e,
            exc_info=True,
        )
        return None


def limpiar_texto(texto: str) -> str:
    if not texto:
        return texto
    texto = re.sub(r"\s+", " ", texto)
    texto = texto.strip()
    texto = "".join(c for c in texto if c.isprintable() or c in "\n\t")
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto


class DocumentCardSchema(BaseModel):
    summary: str = Field(description="Resumen ejecutivo del documento en exactamente 2 líneas.")
    topics: List[str] = Field(description="Lista de 5 palabras clave del documento.")
    usage_guide: str = Field(description="Frase que indica para qué usar este documento.")
    hypothetical_questions: List[str] = Field(description="Tres preguntas que este documento responde perfectamente (HyDE).")


def generate_document_card(text_content: str, filename: str) -> Dict[str, Any]:
    truncated_text = text_content[:65000] if len(text_content) > 65000 else text_content
    prompt = f"""Analiza el siguiente texto extraído del documento "{filename}" y genera la ficha (document card) con:
- Un resumen ejecutivo del documento en exactamente 2 líneas.
- Cinco palabras clave (topics).
- Una frase usage_guide que empiece por "Usa este documento para responder preguntas sobre..." y complete el tema.
- Tres preguntas hipotéticas que este documento responde perfectamente (para búsqueda HyDE).

Texto del documento:
---
{truncated_text}
---"""
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        flash_model = gemini_flash_model_id()
        if api_key:
            llm = ChatGoogleGenerativeAI(model=flash_model, google_api_key=api_key, temperature=0)
        else:
            credentials, project_id = get_credentials_and_project()
            if not credentials or not project_id:
                return {}
            llm = ChatGoogleGenerativeAI(
                model=flash_model,
                credentials=credentials,
                project=project_id,
                location="global",
                temperature=0,
            )
        structured_llm = llm.with_structured_output(DocumentCardSchema)
        result = structured_llm.invoke(prompt)
        return result.model_dump() if result else {}
    except Exception as e:
        logger.warning("Error generating document card for %s: %s", filename, e)
        return {}


def _slug_for_competency_compare(label: str) -> str:
    """Clave normalizada para detectar nombres duplicados o casi idénticos."""
    s = (label or "").lower().strip()
    return re.sub(r"[^a-z0-9áéíóúñü]+", "", s, flags=re.IGNORECASE)


def _sanitize_extracted_competency_tree(tree: "ExtractedCompetencyTree") -> "ExtractedCompetencyTree":
    """Evita etiquetas duplicadas y descripciones de resultado idénticas entre subcompetencias."""
    from schemas import ExtractedCompetencyTree, ExtractedLearningOutcome, ExtractedSubcompetency

    main_name = " ".join((tree.competency_name or "").split())
    seen: set[str] = {_slug_for_competency_compare(main_name)}
    new_subs: list[ExtractedSubcompetency] = []

    for i, sub in enumerate(tree.subcompetencies):
        original = (sub.name or "").strip()
        name = " ".join(original.split())
        slug = _slug_for_competency_compare(name)
        counter = 2
        while not slug or slug in seen:
            name = f"{original or f'Ámbito {i + 1}'} — faceta {counter}"
            slug = _slug_for_competency_compare(name)
            counter += 1
        seen.add(slug)
        desc = " ".join((sub.learning_outcomes[0].description or "").split())
        new_subs.append(
            ExtractedSubcompetency(
                name=name,
                learning_outcomes=[ExtractedLearningOutcome(description=desc)],
            )
        )

    if (
        len(new_subs) == 2
        and _slug_for_competency_compare(new_subs[0].learning_outcomes[0].description)
        == _slug_for_competency_compare(new_subs[1].learning_outcomes[0].description)
    ):
        d1 = new_subs[1].learning_outcomes[0].description
        d1_unique = (
            f"{d1.rstrip('. ')}. Debe demostrarse aplicando el criterio a «{new_subs[1].name}»."
        )
        new_subs[1] = ExtractedSubcompetency(
            name=new_subs[1].name,
            learning_outcomes=[ExtractedLearningOutcome(description=d1_unique)],
        )

    return ExtractedCompetencyTree(competency_name=main_name, subcompetencies=new_subs)


def extract_document_competencies(text: str) -> Optional["ExtractedCompetencyTree"]:
    """Extrae competencias prácticas y evaluables (1 competencia, 2 subcompetencias, 2 resultados)."""
    from schemas import ExtractedCompetencyTree

    truncated = text[:60000] if len(text) > 60000 else text
    prompt = (
        "Eres diseñador instruccional senior. A partir del TEXTO del documento (no inventes fuera de él), "
        "define competencias útiles en el trabajo real que ese contenido habilita.\n\n"
        "REQUISITOS ESTRICTOS:\n"
        "• La competencia principal debe nombrar un ámbito CONCRETO del documento (norma, proceso, "
        "herramienta, caso o rol). Prohibido dejarla en frases vacías tipo 'competencias generales', "
        "'desarrollo integral', 'comprensión global' o 'conocimientos básicos' sin objeto.\n"
        "• Las DOS subcompetencias deben ser ORTOGONALES: facetas distintas (p. ej. interpretación vs "
        "aplicación, análisis vs verificación, planificación vs comunicación). No repitas la misma idea "
        "con distintas palabras.\n"
        "• Cada resultado de aprendizaje debe ser OBSERVABLE y EVALUABLE: verbo de acción + qué produce "
        "o hace el estudiante + criterio o evidencia verificable (puede calificarse sí/no o con rúbrica corta). "
        "Evita 'comprender', 'sensibilizarse', 'valorar' sin indicar evidencia observable.\n"
        "• Redacta en español. Usa términos que aparezcan o se deduzcan claramente del texto.\n"
        "• No dupliques nombres entre competencia principal y subcompetencias ni entre las dos subcompetencias.\n\n"
        "Devuelve exactamente la estructura pedida (2 subcompetencias, cada una con un solo learning outcome).\n\n"
        f"TEXTO DEL DOCUMENTO:\n---\n{truncated}\n---"
    )
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        flash_model = gemini_flash_model_id()
        if api_key:
            llm = ChatGoogleGenerativeAI(
                model=flash_model, google_api_key=api_key, temperature=0
            )
        else:
            credentials, project_id = get_credentials_and_project()
            if not credentials or not project_id:
                logger.warning("extract_document_competencies: sin credenciales LLM disponibles")
                return None
            llm = ChatGoogleGenerativeAI(
                model=flash_model,
                credentials=credentials,
                project=project_id,
                location="global",
                temperature=0,
            )
        structured_llm = llm.with_structured_output(ExtractedCompetencyTree)
        result = structured_llm.invoke(prompt)
        if not result:
            return None
        return _sanitize_extracted_competency_tree(result)
    except Exception as e:
        logger.warning("Error extrayendo competencias del documento: %s", e)
        return None


async def save_extracted_competencies(
    tree: "ExtractedCompetencyTree",
    document_id: str,
) -> None:
    """Persiste un ExtractedCompetencyTree en la BD de competencias.

    Elimina primero cualquier competencia previa con el mismo ``document_id`` para
    evitar duplicados al reprocesar el mismo PDF (CASCADE borra subcompetencias,
    resultados, evidencias y progreso vinculados a esas filas).
    """
    from database import AsyncSessionLocal, init_db
    from models import Competency, CompetencyType, LearningOutcome, Subcompetency
    from sqlalchemy import delete

    doc_key = (document_id or "").strip()
    if not doc_key:
        logger.warning("save_extracted_competencies: document_id vacío, abortando")
        return

    await init_db()

    async with AsyncSessionLocal() as session:
        await session.execute(delete(Competency).where(Competency.document_id == doc_key))
        await session.flush()

        competency = Competency(
            name=tree.competency_name,
            type=CompetencyType.GENERAL,
            document_id=doc_key,
        )
        session.add(competency)
        await session.flush()

        for sub_data in tree.subcompetencies:
            sub = Subcompetency(
                competency_id=competency.id,
                name=sub_data.name,
            )
            session.add(sub)
            await session.flush()

            for lo_data in sub_data.learning_outcomes:
                lo = LearningOutcome(
                    subcompetency_id=sub.id,
                    description=lo_data.description,
                    weight=1.0,
                )
                session.add(lo)

        await session.commit()
        saved_id = competency.id
    logger.info(
        "Competencias guardadas en BD para documento '%s' (competency_id=%d)",
        document_id,
        saved_id,
    )


def persist_competencies_from_chunk_documents(documents: List[Document]) -> None:
    """Por cada ``source`` en chunks de texto, extrae y persiste competencias en BD.

    Los chunks deben tener ``metadata['source']`` igual a la clave del
    ``document_registry`` (nombre lógico del PDF), alineada con
    ``Competency.document_id``.
    """
    from collections import defaultdict

    text_by_source: Dict[str, List[str]] = defaultdict(list)
    for doc in documents:
        if doc.metadata.get("type") != "text":
            continue
        src = doc.metadata.get("source")
        if not src:
            continue
        text_by_source[str(src)].append(doc.page_content or "")

    for filename, parts in text_by_source.items():
        summary_text = "\n".join(parts)[:60000]
        if not summary_text.strip():
            logger.warning(
                "persist_competencies_from_chunk_documents: sin texto para '%s'",
                filename,
            )
            continue
        try:
            tree = extract_document_competencies(summary_text)
            if tree:
                asyncio.run(save_extracted_competencies(tree, filename))
            else:
                logger.warning(
                    "No se pudieron extraer competencias (LLM) para '%s'",
                    filename,
                )
        except Exception as e:
            logger.warning(
                "Error persistiendo competencias para '%s': %s",
                filename,
                e,
                exc_info=True,
            )


def procesar_pdf(
    ruta_archivo: str,
    extract_images: bool = True,
    max_tokens: int = 65535,
    session_id: Optional[str] = None,
    document_registry: Optional[Dict[str, Any]] = None,
    logical_filename: Optional[str] = None,
) -> Tuple[List[Document], Dict[str, Any]]:
    """Procesa un PDF y retorna (lista de documentos, document_registry actualizado).

    Si se pasa ``logical_filename`` (p. ej. el nombre original del upload),
    se usa como clave en el registro y en metadata ``source`` de los chunks.
    Si no, se usa el basename del path temporal (útil solo cuando coincide).
    """
    document_registry = document_registry or {}
    try:
        if logical_filename and str(logical_filename).strip():
            nombre_archivo = Path(str(logical_filename).strip()).name
        else:
            nombre_archivo = Path(ruta_archivo).name
        all_documents = []

        loader = PyPDFLoader(ruta_archivo)
        documents = loader.load()
        for doc in documents:
            if doc.page_content:
                doc.page_content = limpiar_texto(doc.page_content)

        n_pages = len(documents)
        enable_document_card = _env_flag("RAG_ENABLE_DOCUMENT_CARD", True)
        if n_pages <= 100:
            sample_pages = documents
        else:
            first_50 = documents[:50]
            mid_start = (n_pages // 2) - 12
            middle_25 = documents[mid_start : mid_start + 25]
            last_25 = documents[-25:]
            sample_pages = first_50 + middle_25 + last_25
        sample_text = "\n\n".join(doc.page_content for doc in sample_pages if doc.page_content)
        document_card: Dict[str, Any] = {}
        if enable_document_card and sample_text:
            document_card = generate_document_card(sample_text, nombre_archivo)

        if document_card:
            document_registry[nombre_archivo] = document_card
        else:
            # El dashboard filtra por claves del registro; sin entrada no aparecen
            # competencias aunque existan en BD y en Chroma.
            document_registry[nombre_archivo] = {
                "summary": "",
                "topics": [],
                "usage_guide": "",
                "hypothetical_questions": [],
            }

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
            length_function=len,
        )
        splits = text_splitter.split_documents(documents)
        for split in splits:
            split.metadata["source"] = nombre_archivo
            split.metadata["type"] = "text"
            if document_card:
                split.metadata["doc_summary"] = document_card.get("summary", "")
                split.metadata["doc_usage_guide"] = document_card.get("usage_guide", "")
            if "page" not in split.metadata:
                for doc in documents:
                    if doc.page_content and doc.page_content in split.page_content and "page" in doc.metadata:
                        split.metadata["page"] = doc.metadata["page"]
                        break
        all_documents.extend(splits)

        if document_card and document_card.get("hypothetical_questions"):
            for i, question in enumerate(document_card["hypothetical_questions"]):
                all_documents.append(Document(
                    page_content=question,
                    metadata={
                        "source": nombre_archivo,
                        "type": "hyde",
                        "hyde_index": i + 1,
                        "doc_summary": document_card.get("summary", ""),
                        "doc_usage_guide": document_card.get("usage_guide", ""),
                    }
                ))

        max_pages_for_images = _env_int("RAG_MAX_PAGES_FOR_IMAGES", 60)
        max_images_per_pdf = _env_int("RAG_MAX_IMAGES_PER_PDF", 12)
        enable_images = _env_flag("RAG_ENABLE_IMAGE_EXTRACTION", True)
        should_extract_images = extract_images and enable_images and n_pages <= max_pages_for_images

        if should_extract_images:
            images = extract_images_from_pdf(ruta_archivo)
            if images:
                images = images[:max_images_per_pdf]
                def process_one(item: Tuple[int, bytes, int, str]) -> Tuple[int, Optional[Tuple[str, int, str]]]:
                    i, image_bytes, page_num, image_id = item
                    desc = describe_image_with_gemini(
                        image_bytes,
                        context=f"Página {page_num} del documento '{nombre_archivo}'",
                        max_tokens=max_tokens
                    )
                    return (i, (desc, page_num, image_id) if desc else None)

                results_by_index: List[Optional[Tuple[str, int, str]]] = [None] * len(images)
                img_workers = _bounded_env_int("RAG_IMAGE_DESCRIPTION_WORKERS", 8, 1, 16)
                pool_workers = min(img_workers, len(images))
                with ThreadPoolExecutor(max_workers=max(1, pool_workers)) as executor:
                    futures = {executor.submit(process_one, (i, ib, pn, iid)): i
                              for i, (ib, pn, iid) in enumerate(images)}
                    for future in as_completed(futures):
                        try:
                            idx, res = future.result()
                            results_by_index[idx] = res
                        except _IMAGE_TASK_ERRORS as e:
                            logger.warning(
                                "PDF imagen (Gemini paralelo): %s: %s — archivo=%s",
                                type(e).__name__,
                                e,
                                nombre_archivo,
                                exc_info=True,
                            )
                for result in results_by_index:
                    if result:
                        desc, page_num, image_id = result
                        all_documents.append(Document(
                            page_content=f"[IMAGEN - {image_id}]\n{desc}",
                            metadata={"source": nombre_archivo, "type": "image", "page": page_num, "image_id": image_id}
                        ))

        for doc in all_documents:
            for key, value in list(doc.metadata.items()):
                if isinstance(value, list):
                    doc.metadata[key] = ", ".join(str(v) for v in value)
                elif isinstance(value, dict):
                    doc.metadata[key] = str(value)
                elif not isinstance(value, (str, int, float, bool)):
                    doc.metadata[key] = str(value) if value is not None else ""

        return all_documents, document_registry
    except DocumentProcessingError:
        raise
    except _PDF_LOAD_ERRORS as e:
        logger.error(
            "PDF carga o parseo (PyPDF/pdfminer): %s: %s — archivo=%s",
            type(e).__name__,
            e,
            ruta_archivo,
            exc_info=True,
        )
        raise DocumentProcessingError(
            f"Error de lectura o formato PDF ({type(e).__name__}): {e}"
        ) from e
    except (RuntimeError, OSError, MemoryError, TypeError, KeyError) as e:
        logger.error(
            "PDF post-procesamiento (chunks, metadatos o imágenes): %s: %s — archivo=%s",
            type(e).__name__,
            e,
            ruta_archivo,
            exc_info=True,
        )
        raise DocumentProcessingError(
            f"Error procesando contenido del PDF ({type(e).__name__}): {e}"
        ) from e


def create_document_tool(vector_store: Any, filename: str, usage_guide: str) -> Optional[Any]:
    try:
        filename_sanitized = re.sub(r"[^a-zA-Z0-9]", "_", Path(filename).stem).strip("_").lower()
        tool_name = f"search_document_{filename_sanitized}"
        retriever = vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 20, "lambda_mult": 0.5, "filter": {"source": filename}}
        )
        description = usage_guide or f"Usa esta herramienta para buscar información en el documento '{filename}'."
        return create_retriever_tool(retriever=retriever, name=tool_name, description=description)
    except Exception as e:
        logger.warning("Error creating document tool: %s", e)
        return None


def _chroma_persist_directory(session_id: Optional[str]) -> str:
    """Ruta absoluta del directorio Chroma persistente para una sesión.

    Crea **tanto** el directorio base como el específico de la sesión
    (`exist_ok=True`). Es importante que el subdirectorio exista antes de que
    ChromaDB instancie su `PersistentClient`: en la versión Rust-backed
    (chromadb >= 1.x) si el directorio no existe en el momento de abrir el
    SQLite, la primera escritura falla con `SQLITE_READONLY_DBMOVED`
    (code 1032 = "attempt to write a readonly database"), porque ChromaDB
    detecta que el inode del fichero ha cambiado entre apertura y escritura.
    Pre-creando el directorio garantizamos un inode estable para `chroma.sqlite3`.
    """
    base = os.path.join(os.path.dirname(__file__), "data", "chroma_db")
    persist_directory = os.path.join(base, session_id or "default")
    os.makedirs(persist_directory, exist_ok=True)
    return persist_directory


def initialize_vector_store(
    documents: Optional[List[Document]] = None,
    existing_vector_store: Optional[Any] = None,
    session_id: Optional[str] = None,
) -> Optional[Any]:
    persist_directory = _chroma_persist_directory(session_id)
    try:
        embeddings = get_embeddings()
        if not embeddings:
            logger.warning(
                "Chroma omitido: embeddings Google no inicializados (revisar credenciales/API). session_id=%s",
                session_id,
            )
            return None
        if documents is None or len(documents) == 0:
            if os.path.exists(persist_directory) and os.listdir(persist_directory):
                return Chroma(persist_directory=persist_directory, embedding_function=embeddings)
            return existing_vector_store

        total_docs = len(documents)
        batch_size = _bounded_env_int("RAG_VECTOR_BATCH_SIZE", 40, 5, 200)
        if existing_vector_store is None:
            # En todos los casos abrimos primero un cliente persistente sobre el
            # directorio (que ya existe gracias a `_chroma_persist_directory`) y
            # luego añadimos en lotes. Evitamos `Chroma.from_documents` con
            # `persist_directory` porque en chromadb 1.x con backend Rust ese
            # camino dispara `SQLITE_READONLY_DBMOVED` cuando el SQLite se crea
            # implícitamente durante la primera escritura.
            vector_store = Chroma(
                persist_directory=persist_directory,
                embedding_function=embeddings,
            )
        else:
            vector_store = existing_vector_store

        for i in range(0, total_docs, batch_size):
            batch = documents[i : i + batch_size]
            vector_store.add_documents(batch)
        return vector_store
    except _VECTOR_STORE_ERRORS as e:
        logger.error(
            "Chroma vector store (persist=%s, session_id=%s): %s: %s",
            persist_directory,
            session_id,
            type(e).__name__,
            e,
            exc_info=True,
        )
        return None


async def initialize_vector_store_async(
    documents: Optional[List[Document]] = None,
    existing_vector_store: Optional[Any] = None,
    session_id: Optional[str] = None,
) -> Optional[Any]:
    """Versión no bloqueante para rutas FastAPI: delega en el pool de hilos RAG."""
    return await _run_in_rag_pool(
        initialize_vector_store,
        documents,
        existing_vector_store,
        session_id,
    )


async def procesar_pdf_async(
    ruta_archivo: str,
    extract_images: bool = True,
    max_tokens: int = 65535,
    session_id: Optional[str] = None,
    document_registry: Optional[Dict[str, Any]] = None,
    logical_filename: Optional[str] = None,
) -> Tuple[List[Document], Dict[str, Any]]:
    """Versión no bloqueante para FastAPI: mismo contrato que `procesar_pdf`."""
    return await _run_in_rag_pool(
        procesar_pdf,
        ruta_archivo,
        extract_images=extract_images,
        max_tokens=max_tokens,
        session_id=session_id,
        document_registry=document_registry,
        logical_filename=logical_filename,
    )


def initialize_agent(
    vector_store: Any,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    session_id: Optional[str] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    document_registry: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    if vector_store is None:
        return None
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        pro_model = gemini_pro_model_id()
        if api_key:
            llm = ChatGoogleGenerativeAI(
                model=pro_model,
                temperature=temperature,
                max_output_tokens=max_tokens,
                api_key=api_key,
            )
        else:
            credentials, project_id = get_credentials_and_project()
            if not credentials or not project_id:
                return None
            llm = ChatGoogleGenerativeAI(
                model=pro_model,
                temperature=temperature,
                max_output_tokens=max_tokens,
                vertexai=True,
                project=project_id,
                location="global",
            )

        tools = []
        if document_registry:
            for filename, card in document_registry.items():
                tool = create_document_tool(vector_store, filename, card.get("usage_guide", ""))
                if tool:
                    tools.append(tool)

        general_retriever = vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 20, "lambda_mult": 0.5}
        )
        tools.append(create_retriever_tool(
            retriever=general_retriever,
            name="search_all_documents",
            description="Busca información en TODOS los documentos disponibles."
        ))

        user_facts_section = ""
        if session_id:
            try:
                um = UserMemoryManager()
                uf = um.get_user_facts_formatted(session_id)
                if uf:
                    user_facts_section = f"\n\nINFORMACIÓN CONOCIDA SOBRE EL USUARIO:\n{uf}\nUsa esta información para personalizar tus respuestas cuando sea relevante."
            except Exception:
                pass

        tool_descriptions = "\n".join(f"  - **{t.name}**: {t.description}" for t in tools)
        system_prompt = f"""Eres un asistente educativo avanzado con acceso a una biblioteca de documentos específicos.{user_facts_section}

TIENES ACCESO A LAS SIGUIENTES HERRAMIENTAS DE BÚSQUEDA:
{tool_descriptions}

TU PROCESO DE TRABAJO:
1. Elige la herramienta más apropiada según la pregunta del usuario.
2. Si la pregunta se refiere a un documento específico, usa la herramienta de ese documento.
3. Si la pregunta es general, usa "search_all_documents".
4. Formula tu respuesta basándote EXCLUSIVAMENTE en la información recuperada.

INSTRUCCIONES: Basa tu respuesta en el contexto recuperado. Cita fuentes con [nombre_archivo]. Si no está disponible, admítelo."""

        messages = []
        if chat_history:
            for msg in chat_history:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg.get("content", "")))

        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=system_prompt,
            name="educational_rag_agent",
        )
        return agent
    except Exception as e:
        logger.exception("Error initializing agent: %s", e)
        return None
