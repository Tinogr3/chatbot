"""
Motor RAG (backend) - Sin dependencias de Streamlit.
"""
import os
import re
import time
import base64
import tempfile
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from pydantic import BaseModel, Field
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_core.tools.retriever import create_retriever_tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage

from config import get_credentials_and_project
from user_memory import UserMemoryManager

logger = logging.getLogger(__name__)

_embeddings_cache: Optional[GoogleGenerativeAIEmbeddings] = None


def extract_text(content) -> str:
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
            elif isinstance(item, str):
                text_parts.append(item)
        return "".join(text_parts)
    return str(content) if content is not None else ""


def get_gemini_vision_model(max_tokens: int = 65535):
    try:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
        if api_key:
            return ChatGoogleGenerativeAI(
                model="gemini-3-pro-preview",
                google_api_key=api_key,
                temperature=1,
                max_output_tokens=max_tokens
            )
        credentials, project_id = get_credentials_and_project()
        if credentials and project_id:
            return ChatGoogleGenerativeAI(
                model="gemini-3-pro-preview",
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
                except Exception:
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
        except Exception as e:
            logger.warning("Error extracting images: %s", e)
    except Exception as e:
        logger.warning("Error extracting images: %s", e)
    return images


def get_embeddings() -> Optional[GoogleGenerativeAIEmbeddings]:
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache
    try:
        credentials, project_id = get_credentials_and_project()
        if not project_id:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
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
    except Exception as e:
        logger.warning("Error initializing embeddings: %s", e)
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


def generate_document_card(text_content: str, filename: str) -> dict:
    truncated_text = text_content[:15000] if len(text_content) > 15000 else text_content
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
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
        if api_key:
            llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", google_api_key=api_key, temperature=0)
        else:
            credentials, project_id = get_credentials_and_project()
            if not credentials or not project_id:
                return {}
            llm = ChatGoogleGenerativeAI(
                model="gemini-3-flash-preview",
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


def procesar_pdf(
    ruta_archivo: str,
    extract_images: bool = True,
    max_tokens: int = 65535,
    session_id: Optional[str] = None,
    document_registry: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Document], Dict[str, Any]]:
    """Procesa un PDF y retorna (lista de documentos, document_registry actualizado)."""
    document_registry = document_registry or {}
    try:
        nombre_archivo = Path(ruta_archivo).name
        all_documents = []

        loader = PyPDFLoader(ruta_archivo)
        documents = loader.load()
        for doc in documents:
            if doc.page_content:
                doc.page_content = limpiar_texto(doc.page_content)

        sample_pages = documents[:10]
        sample_text = "\n\n".join(doc.page_content for doc in sample_pages if doc.page_content)
        document_card = generate_document_card(sample_text, nombre_archivo)

        if document_card:
            document_registry[nombre_archivo] = document_card

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

        if extract_images:
            images = extract_images_from_pdf(ruta_archivo)
            if images:
                def process_one(item: Tuple[int, bytes, int, str]) -> Tuple[int, Optional[Tuple[str, int, str]]]:
                    i, image_bytes, page_num, image_id = item
                    desc = describe_image_with_gemini(
                        image_bytes,
                        context=f"Página {page_num} del documento '{nombre_archivo}'",
                        max_tokens=max_tokens
                    )
                    return (i, (desc, page_num, image_id) if desc else None)

                results_by_index: List[Optional[Tuple[str, int, str]]] = [None] * len(images)
                with ThreadPoolExecutor(max_workers=min(4, len(images))) as executor:
                    futures = {executor.submit(process_one, (i, ib, pn, iid)): i
                              for i, (ib, pn, iid) in enumerate(images)}
                    for future in as_completed(futures):
                        try:
                            idx, res = future.result()
                            results_by_index[idx] = res
                        except Exception as e:
                            logger.warning("Error processing image: %s", e)
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
    except Exception as e:
        logger.exception("Error processing PDF: %s", e)
        return [], document_registry


def create_document_tool(vector_store, filename: str, usage_guide: str):
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
    base = os.path.join(os.path.dirname(__file__), "data", "chroma_db")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, session_id or "default")


def initialize_vector_store(
    documents: Optional[List[Document]] = None,
    existing_vector_store=None,
    session_id: Optional[str] = None,
) -> Optional[Any]:
    persist_directory = _chroma_persist_directory(session_id)
    try:
        embeddings = get_embeddings()
        if not embeddings:
            return None
        if documents is None or len(documents) == 0:
            if os.path.exists(persist_directory) and os.listdir(persist_directory):
                return Chroma(persist_directory=persist_directory, embedding_function=embeddings)
            return existing_vector_store

        total_docs = len(documents)
        batch_size = 5
        if existing_vector_store is None:
            if os.path.exists(persist_directory) and os.listdir(persist_directory):
                vector_store = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
            else:
                first_batch = documents[: min(batch_size, total_docs)]
                vector_store = Chroma.from_documents(
                    documents=first_batch,
                    embedding=embeddings,
                    persist_directory=persist_directory
                )
                for i in range(batch_size, total_docs, batch_size):
                    batch = documents[i : i + batch_size]
                    vector_store.add_documents(batch)
                    if i + batch_size < total_docs:
                        time.sleep(0.5)
                return vector_store
        else:
            vector_store = existing_vector_store

        for i in range(0, total_docs, batch_size):
            batch = documents[i : i + batch_size]
            vector_store.add_documents(batch)
            if i + batch_size < total_docs:
                time.sleep(0.5)
        return vector_store
    except Exception as e:
        logger.exception("Error initializing vector store: %s", e)
        return None


def initialize_agent(
    vector_store,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    session_id: Optional[str] = None,
    chat_history: Optional[list] = None,
    document_registry: Optional[dict] = None,
):
    if vector_store is None:
        return None
    try:
        credentials, project_id = get_credentials_and_project()
        if not project_id:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
            if not api_key:
                return None
            llm = ChatGoogleGenerativeAI(
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-3-pro-preview",
                temperature=temperature,
                max_output_tokens=max_tokens,
                api_key=api_key
            )
        else:
            llm = ChatGoogleGenerativeAI(
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-3-pro-preview",
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
