"""
Módulo de motor RAG (Retrieval Augmented Generation).
Contiene la lógica de LangChain, embeddings, procesamiento de PDFs y creación de chains.
"""
import os
import re
import json
import time
import base64
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools.retriever import create_retriever_tool
from langgraph.prebuilt import create_react_agent

from config import get_credentials_and_project
from user_memory import UserMemoryManager


def get_gemini_vision_model():
    """Obtiene el modelo Gemini con capacidades de visión para describir imágenes."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
        if api_key:
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-pro",
                google_api_key=api_key,
                temperature=1,
                max_tokens=16384
            )
        
        credentials, project_id = get_credentials_and_project()
        if credentials and project_id:
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-pro",
                credentials=credentials,
                project=project_id,
                temperature=1,
                max_tokens=16384
            )
    except Exception as e:
        print(f"Error inicializando modelo de visión: {e}")
    return None


def describe_image_with_gemini(image_bytes: bytes, context: str = "") -> str:
    """
    Genera una descripción textual de una imagen usando Gemini.
    
    Args:
        image_bytes: Bytes de la imagen.
        context: Contexto adicional (ej: nombre del documento).
    
    Returns:
        Descripción textual de la imagen.
    """
    model = get_gemini_vision_model()
    if not model:
        return ""
    
    try:
        # Codificar imagen en base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        prompt = f"""Analiza esta imagen de un documento educativo y proporciona una descripción detallada y útil para el aprendizaje.

Incluye:
- Tipo de contenido visual (diagrama, gráfico, tabla, fórmula, ilustración, etc.)
- Descripción del contenido principal
- Datos, valores o texto visible relevante
- Relaciones o conceptos que muestra
- Contexto educativo si es evidente

{f'Contexto del documento: {context}' if context else ''}

Responde en español con una descripción clara y concisa."""

        # Crear mensaje con imagen
        from langchain_core.messages import HumanMessage
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                }
            ]
        )
        
        response = model.invoke([message])
        return response.content.strip()
        
    except Exception as e:
        print(f"Error describiendo imagen: {e}")
        return ""


def extract_images_from_pdf(pdf_path: str) -> List[Tuple[bytes, int, str]]:
    """
    Extrae imágenes de un PDF usando unstructured.
    
    Args:
        pdf_path: Ruta al archivo PDF.
    
    Returns:
        Lista de tuplas (image_bytes, page_number, image_id).
    """
    images = []
    
    try:
        from unstructured.partition.pdf import partition_pdf
        from unstructured.documents.elements import Image
        import fitz  # PyMuPDF - más confiable para extraer imágenes
        
        # Usar PyMuPDF para extraer imágenes (más robusto)
        doc = fitz.open(pdf_path)
        
        for page_num, page in enumerate(doc):
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # Filtrar imágenes muy pequeñas (probablemente iconos)
                    if len(image_bytes) > 5000:  # Más de 5KB
                        image_id = f"page{page_num + 1}_img{img_index + 1}"
                        images.append((image_bytes, page_num + 1, image_id))
                except Exception as e:
                    continue
        
        doc.close()
        
    except ImportError:
        print("[RAG] PyMuPDF no disponible, intentando con unstructured...")
        try:
            from unstructured.partition.pdf import partition_pdf
            
            # Crear directorio temporal para imágenes
            with tempfile.TemporaryDirectory() as temp_dir:
                elements = partition_pdf(
                    filename=pdf_path,
                    extract_images_in_pdf=True,
                    extract_image_block_output_dir=temp_dir,
                    strategy="hi_res"
                )
                
                # Buscar imágenes extraídas
                import glob
                for img_path in glob.glob(os.path.join(temp_dir, "*.png")) + \
                               glob.glob(os.path.join(temp_dir, "*.jpg")):
                    with open(img_path, 'rb') as f:
                        image_bytes = f.read()
                    if len(image_bytes) > 5000:
                        img_name = Path(img_path).stem
                        images.append((image_bytes, 1, img_name))
                        
        except Exception as e:
            print(f"Error extrayendo imágenes con unstructured: {e}")
    except Exception as e:
        print(f"Error extrayendo imágenes: {e}")
    
    return images


@st.cache_resource
def get_embeddings():
    """Inicializa el modelo de embeddings de Google Generative AI usando Vertex AI."""
    try:
        credentials, project_id = get_credentials_and_project()
        
        if not project_id:
            # Si no hay credenciales de servicio, intentar con API key
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
            if api_key:
                return GoogleGenerativeAIEmbeddings(
                    model="text-embedding-004",
                    api_key=api_key
                )
            else:
                st.error(
                    "❌ No se encontraron credenciales.\\n\\n"
                    "Opción 1: Coloca un archivo JSON de credenciales de servicio en el directorio.\\n"
                    "Opción 2: Configura GOOGLE_API_KEY o VERTEX_AI_API_KEY en tu archivo .env"
                )
                return None
        
        # Usar Vertex AI con credenciales de servicio
        return GoogleGenerativeAIEmbeddings(
            model="text-embedding-004",
            vertexai=True,
            project=project_id,
            location="us-central1"
        )
    except Exception as e:
        st.error(f"Error al inicializar embeddings: {str(e)}")
        return None


def limpiar_texto(texto: str) -> str:
    """Limpia el texto eliminando espacios excesivos y caracteres extraños."""
    if not texto:
        return texto
    
    # Eliminar espacios múltiples y reemplazar por uno solo
    texto = re.sub(r'\\s+', ' ', texto)
    
    # Eliminar espacios al inicio y final
    texto = texto.strip()
    
    # Eliminar caracteres de control y caracteres extraños (mantener solo imprimibles)
    texto = ''.join(char for char in texto if char.isprintable() or char in '\\n\\t')
    
    # Normalizar saltos de línea múltiples
    texto = re.sub(r'\\n{3,}', '\\n\\n', texto)
    
    return texto


def generate_document_card(text_content: str, filename: str) -> dict:
    """Genera metadatos agénticos (document card) para un documento PDF.

    Usa Gemini 2.0 Flash para analizar el texto y producir un JSON con:
    - summary: resumen ejecutivo de 2 líneas.
    - topics: lista de 5 palabras clave.
    - usage_guide: frase que empieza por "Usa este documento para responder preguntas sobre...".
    - hypothetical_questions: 3 preguntas que el documento responde (técnica HyDE).

    Args:
        text_content: Texto completo (o representativo) del documento.
        filename: Nombre del archivo PDF.

    Returns:
        Diccionario con los metadatos generados, o dict vacío si falla.
    """
    MAX_RETRIES = 2

    # Truncar el texto para no exceder límites del modelo
    truncated_text = text_content[:15000] if len(text_content) > 15000 else text_content

    prompt = f"""Analiza el siguiente texto extraído del documento "{filename}" y devuelve ÚNICAMENTE un objeto JSON (sin bloques de código markdown, sin explicaciones adicionales) con esta estructura exacta:

{{
  "summary": "<Resumen ejecutivo del documento en exactamente 2 líneas>",
  "topics": ["<palabra clave 1>", "<palabra clave 2>", "<palabra clave 3>", "<palabra clave 4>", "<palabra clave 5>"],
  "usage_guide": "Usa este documento para responder preguntas sobre <completar>",
  "hypothetical_questions": [
    "<Pregunta 1 que este documento responde perfectamente>",
    "<Pregunta 2 que este documento responde perfectamente>",
    "<Pregunta 3 que este documento responde perfectamente>"
  ]
}}

Texto del documento:
---
{truncated_text}
---

Recuerda: responde SOLO con el JSON válido, sin ningún texto adicional."""

    try:
        # Obtener credenciales
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")

        if api_key:
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                google_api_key=api_key,
                temperature=0,
            )
        else:
            credentials, project_id = get_credentials_and_project()
            if not credentials or not project_id:
                print("[DocumentCard] No se encontraron credenciales.")
                return {}
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                credentials=credentials,
                project=project_id,
                temperature=0,
            )

        # Intentar generar y parsear, con reintentos
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = llm.invoke(prompt)
                raw = response.content.strip()

                # Limpiar posible bloque markdown ```json ... ```
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"```\s*$", "", raw)

                card = json.loads(raw)

                # Validación básica de campos esperados
                required_keys = {"summary", "topics", "usage_guide", "hypothetical_questions"}
                if not required_keys.issubset(card.keys()):
                    missing = required_keys - card.keys()
                    print(f"[DocumentCard] Intento {attempt}: faltan campos {missing}")
                    continue

                print(f"[DocumentCard] Generada correctamente para '{filename}'")
                return card

            except json.JSONDecodeError as je:
                print(f"[DocumentCard] Intento {attempt}: error parseando JSON — {je}")
                continue

        print(f"[DocumentCard] Fallaron todos los intentos para '{filename}'")
        return {}

    except Exception as e:
        print(f"[DocumentCard] Error inesperado generando card para '{filename}': {e}")
        return {}


def procesar_pdf(ruta_archivo: str, extract_images: bool = True) -> List:
    """Procesa un PDF desde una ruta y retorna los documentos divididos con metadatos.
    
    Args:
        ruta_archivo: Ruta al archivo PDF.
        extract_images: Si True, extrae imágenes y genera descripciones con Gemini.
    
    Returns:
        Lista de documentos (chunks de texto + descripciones de imágenes).
    """
    try:
        nombre_archivo = Path(ruta_archivo).name
        all_documents = []
        
        # === 1. Procesar texto del PDF ===
        loader = PyPDFLoader(ruta_archivo)
        documents = loader.load()

        # Limpiar el texto de cada documento antes de dividir
        for doc in documents:
            if doc.page_content:
                doc.page_content = limpiar_texto(doc.page_content)

        # === 1.5 Generar Document Card (metadatos agénticos) ===
        # Tomar muestra representativa: primeras 10 páginas o 15k caracteres
        sample_pages = documents[:10]
        sample_text = "\n\n".join(
            doc.page_content for doc in sample_pages if doc.page_content
        )

        st.info("🃏 Generando Document Card con metadatos agénticos...")
        document_card = generate_document_card(sample_text, nombre_archivo)

        if document_card:
            st.success(f"✅ Document Card generada para '{nombre_archivo}'")
            # Opción B: Guardar en el registro global de documentos
            if "document_registry" not in st.session_state:
                st.session_state.document_registry = {}
            st.session_state.document_registry[nombre_archivo] = document_card
            
            # Persistir el registro completo en disco
            try:
                with open('document_registry.json', 'w', encoding='utf-8') as f:
                    json.dump(st.session_state.document_registry, f, ensure_ascii=False, indent=2)
                print(f"[Registry] Guardado document_registry.json ({len(st.session_state.document_registry)} documentos)")
            except IOError as e:
                print(f"[Registry] Error guardando document_registry.json: {e}")
        else:
            st.warning("⚠️ No se pudo generar la Document Card. Continuando sin metadatos agénticos.")

        # Dividir documentos usando RecursiveCharacterTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=[
                "\n\n",  # Saltos de párrafo
                "\n",    # Saltos de línea
                ". ",    # Puntos
                "! ",    # Exclamación
                "? ",    # Interrogación
                "; ",    # Punto y coma
                ", ",    # Comas
                " ",     # Espacios
                ""       # Último recurso
            ],
            length_function=len,
        )

        splits = text_splitter.split_documents(documents)
        
        # Asegurar metadatos correctos en cada chunk de texto
        for split in splits:
            split.metadata["source"] = nombre_archivo
            split.metadata["type"] = "text"
            
            # Opción A: Inyectar metadatos agénticos de la Document Card
            if document_card:
                split.metadata["doc_summary"] = document_card.get("summary", "")
                split.metadata["doc_usage_guide"] = document_card.get("usage_guide", "")
            
            if "page" not in split.metadata:
                for doc in documents:
                    if doc.page_content and doc.page_content in split.page_content:
                        if "page" in doc.metadata:
                            split.metadata["page"] = doc.metadata["page"]
                        break
        
        all_documents.extend(splits)
        
        # === 1.7 Crear chunks sintéticos HyDE (Hypothetical Document Embeddings) ===
        if document_card and document_card.get("hypothetical_questions"):
            hyde_questions = document_card["hypothetical_questions"]
            for i, question in enumerate(hyde_questions):
                hyde_doc = Document(
                    page_content=question,
                    metadata={
                        "source": nombre_archivo,
                        "type": "hyde",
                        "hyde_index": i + 1,
                        "doc_summary": document_card.get("summary", ""),
                        "doc_usage_guide": document_card.get("usage_guide", ""),
                    }
                )
                all_documents.append(hyde_doc)
            print(f"[HyDE] {len(hyde_questions)} chunks sintéticos creados para '{nombre_archivo}'")
        
        # === 2. Extraer y describir imágenes ===
        if extract_images:
            st.info("🖼️ Extrayendo y analizando imágenes del PDF...")
            
            images = extract_images_from_pdf(ruta_archivo)
            
            if images:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, (image_bytes, page_num, image_id) in enumerate(images):
                    progress = (i + 1) / len(images)
                    progress_bar.progress(progress)
                    status_text.text(f"Analizando imagen {i + 1}/{len(images)}...")
                    
                    # Generar descripción con Gemini
                    description = describe_image_with_gemini(
                        image_bytes, 
                        context=f"Página {page_num} del documento '{nombre_archivo}'"
                    )
                    
                    if description:
                        # Crear documento con la descripción de la imagen
                        image_doc = Document(
                            page_content=f"[IMAGEN - {image_id}]\n{description}",
                            metadata={
                                "source": nombre_archivo,
                                "type": "image",
                                "page": page_num,
                                "image_id": image_id
                            }
                        )
                        all_documents.append(image_doc)
                    
                    # Pequeña pausa para no saturar la API
                    time.sleep(0.5)
                
                progress_bar.empty()
                status_text.empty()
                st.success(f"✅ Analizadas {len(images)} imágenes del PDF.")
        
        # === Sanitizar metadatos para Chroma/SQLite ===
        # SQLite solo acepta str, int, float, bool — no listas ni dicts
        for doc in all_documents:
            for key, value in list(doc.metadata.items()):
                if isinstance(value, list):
                    doc.metadata[key] = ", ".join(str(v) for v in value)
                elif isinstance(value, dict):
                    doc.metadata[key] = str(value)
                elif not isinstance(value, (str, int, float, bool)):
                    doc.metadata[key] = str(value) if value is not None else ""
        
        return all_documents
    except Exception as e:
        st.error(f"Error al procesar PDF: {str(e)}")
        return []


def create_document_tool(vector_store, filename: str, usage_guide: str):
    """Crea una herramienta de búsqueda LangChain filtrada a un documento específico.

    Genera un retriever tool cuya descripción es el usage_guide de la Document Card,
    permitiendo a un agente decidir automáticamente cuándo usar cada herramienta.

    Args:
        vector_store: El vector store de Chroma con los embeddings.
        filename: Nombre del archivo PDF (usado como filtro y para el nombre de la herramienta).
        usage_guide: Descripción generada por la IA (campo usage_guide de la Document Card).

    Returns:
        Un Tool de LangChain listo para usar en un agente, o None si falla.
    """
    try:
        # Sanitizar el nombre del archivo para usarlo como nombre de herramienta
        filename_sanitized = re.sub(r'[^a-zA-Z0-9]', '_', Path(filename).stem).strip('_').lower()
        tool_name = f"search_document_{filename_sanitized}"

        # Crear retriever filtrado exclusivamente a este documento
        retriever = vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 5,
                "fetch_k": 20,
                "lambda_mult": 0.5,
                "filter": {"source": filename}
            }
        )

        # Usar el usage_guide como descripción; fallback genérico si está vacío
        description = usage_guide if usage_guide else (
            f"Usa esta herramienta para buscar información en el documento '{filename}'."
        )

        tool = create_retriever_tool(
            retriever=retriever,
            name=tool_name,
            description=description,
        )

        print(f"[ToolFactory] Herramienta '{tool_name}' creada para '{filename}'")
        return tool

    except Exception as e:
        print(f"[ToolFactory] Error creando herramienta para '{filename}': {e}")
        return None


def initialize_vector_store(
    documents: List = None, 
    existing_vector_store=None,
    persist_directory: str = "./chroma_db"
) -> Optional[object]:
    """Inicializa o actualiza el vector store de Chroma procesando documentos en lotes.
    
    Args:
        documents: Lista de documentos a procesar (None para solo cargar existente)
        existing_vector_store: Vector store existente al que agregar documentos (None para crear nuevo)
        persist_directory: Directorio donde persistir la base de datos ChromaDB
    
    Returns:
        El objeto vector_store creado o actualizado
    
    Nota: Usa persistencia local en disco para mantener los embeddings entre sesiones.
    """
    try:
        embeddings = get_embeddings()
        if not embeddings:
            return None
        
        # Si no hay documentos, intentar cargar base existente
        if documents is None or len(documents) == 0:
            # Verificar si existe la base de datos
            if os.path.exists(persist_directory) and os.listdir(persist_directory):
                st.info("📂 Cargando base de datos de vectores existente...")
                vector_store = Chroma(
                    persist_directory=persist_directory,
                    embedding_function=embeddings
                )
                st.success("✅ Base de datos cargada correctamente.")
                return vector_store
            else:
                return existing_vector_store
        
        total_docs = len(documents)
        batch_size = 5
        num_batches = (total_docs + batch_size - 1) // batch_size  # Redondeo hacia arriba
        
        # Crear barra de progreso
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Si no existe vector store, verificar si hay uno persistido o crear nuevo
        if existing_vector_store is None:
            # Verificar si ya existe una base de datos persistida
            if os.path.exists(persist_directory) and os.listdir(persist_directory):
                st.info("📂 Cargando base de datos existente y agregando nuevos documentos...")
                vector_store = Chroma(
                    persist_directory=persist_directory,
                    embedding_function=embeddings
                )
            else:
                # Crear nuevo vector store con persistencia
                first_batch = documents[0:min(batch_size, total_docs)]
                vector_store = Chroma.from_documents(
                    documents=first_batch,
                    embedding=embeddings,
                    persist_directory=persist_directory
                )
                
                # Actualizar barra de progreso para el primer lote
                if len(first_batch) > 0:
                    progress = len(first_batch) / total_docs
                    progress_bar.progress(progress)
                    status_text.text(f"Procesando lote 1/{num_batches} ({len(first_batch)} documentos)...")
                    if total_docs > batch_size:
                        time.sleep(2)
                
                # Agregar documentos restantes en lotes
                for i in range(batch_size, total_docs, batch_size):
                    batch = documents[i:i + batch_size]
                    batch_num = (i // batch_size) + 1
                    
                    # Actualizar barra de progreso
                    progress = (i + len(batch)) / total_docs
                    progress_bar.progress(progress)
                    status_text.text(f"Procesando lote {batch_num + 1}/{num_batches} ({len(batch)} documentos)...")
                    
                    # Agregar lote al vector store
                    vector_store.add_documents(batch)
                    
                    # Esperar 2 segundos antes del siguiente lote (excepto en el último)
                    if i + batch_size < total_docs:
                        time.sleep(2)
                
                # Completar barra de progreso
                progress_bar.progress(1.0)
                status_text.text(f"✅ Procesados {total_docs} documentos en {num_batches} lotes.")
                time.sleep(0.5)
                status_text.empty()
                progress_bar.empty()
                
                return vector_store
        else:
            vector_store = existing_vector_store
        
        # Agregar documentos al vector store existente en lotes
        for i in range(0, total_docs, batch_size):
            batch = documents[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            # Actualizar barra de progreso
            progress = (i + len(batch)) / total_docs
            progress_bar.progress(progress)
            status_text.text(f"Procesando lote {batch_num}/{num_batches} ({len(batch)} documentos)...")
            
            # Agregar lote al vector store
            vector_store.add_documents(batch)
            
            # Esperar 2 segundos antes del siguiente lote (excepto en el último)
            if i + batch_size < total_docs:
                time.sleep(2)
        
        # Completar barra de progreso
        progress_bar.progress(1.0)
        status_text.text(f"✅ Procesados {total_docs} documentos en {num_batches} lotes.")
        time.sleep(0.5)  # Pequeña pausa para mostrar el mensaje final
        status_text.empty()
        progress_bar.empty()
        
        return vector_store
    except Exception as e:
        st.error(f"Error al inicializar vector store: {str(e)}")
        import traceback
        st.error(f"Detalles: {traceback.format_exc()}")
        return None


def initialize_conversation_chain(
    vector_store, 
    temperature: float = 0.7, 
    max_tokens: int = 2048,
    session_id: str = None,
    chat_history: list = None
):
    """Inicializa la cadena de conversación con memoria.
    
    Args:
        vector_store: El vector store a usar para retrieval
        temperature: Nivel de creatividad del modelo
        max_tokens: Límite de tokens en la respuesta
        session_id: ID de sesión para cargar hechos del usuario
        chat_history: Lista de mensajes previos para poblar la memoria
    
    Returns:
        La chain de conversación configurada
    """
    try:
        if vector_store is None:
            return None
        
        # Inicializar el modelo de chat
        credentials, project_id = get_credentials_and_project()
        
        if not project_id:
            # Si no hay credenciales de servicio, intentar con API key
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
            if not api_key:
                st.error(
                    "❌ No se encontraron credenciales para el modelo de chat.\\n\\n"
                    "Opción 1: Coloca un archivo JSON de credenciales de servicio en el directorio.\\n"
                    "Opción 2: Configura GOOGLE_API_KEY o VERTEX_AI_API_KEY en tu archivo .env"
                )
                return None
            
            llm = ChatGoogleGenerativeAI(
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-2.5-pro",
                temperature=temperature,
                max_output_tokens=max_tokens,
                api_key=api_key
            )
        else:
            # Usar Vertex AI con credenciales de servicio
            llm = ChatGoogleGenerativeAI(
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-2.5-pro",
                temperature=temperature,
                max_output_tokens=max_tokens,
                vertexai=True,
                project=project_id,
                location="us-central1"
            )
        
        # Configurar memoria para mantener el historial de conversación
        # ConversationBufferMemory gestiona automáticamente el chat_history
        # y lo pasa a ConversationalRetrievalChain para permitir preguntas de seguimiento
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer"
        )
        
        # Poblar la memoria con el historial guardado si existe
        if chat_history:
            for msg in chat_history:
                if msg.get('role') == 'user':
                    memory.chat_memory.add_user_message(msg.get('content', ''))
                elif msg.get('role') == 'assistant':
                    memory.chat_memory.add_ai_message(msg.get('content', ''))
        
        # Obtener hechos del usuario si hay session_id
        user_facts_section = ""
        if session_id:
            try:
                user_memory = UserMemoryManager()
                user_facts = user_memory.get_user_facts_formatted(session_id)
                if user_facts:
                    user_facts_section = f"""\n\nINFORMACIÓN CONOCIDA SOBRE EL USUARIO:
{user_facts}

Usa esta información para personalizar tus respuestas cuando sea relevante."""
            except Exception as e:
                print(f"Error cargando hechos del usuario: {e}")
        
        # System prompt personalizado mejorado
        system_template = f"""Eres un asistente educativo avanzado. {user_facts_section}

TU PROCESO DE PENSAMIENTO (Cadena de Razonamiento):
Antes de generar tu respuesta final, debes pensar internamente siguiendo estos pasos:
1.  **Analizar la Intención:** ¿Qué necesita realmente el usuario? ¿Información factual, explicación conceptual o ayuda práctica?
2.  **Verificar Contexto:** Revisa los fragmentos de documentos proporcionados a continuación.
3.  **Filtrar:** Descarta la información irrelevante del contexto.
4.  **Sintetizar:** Conecta los puntos entre diferentes documentos si es necesario.
5.  **Formular:** Crea la respuesta final citando las fuentes.

INSTRUCCIONES DE RESPUESTA:
- Basa tu respuesta EXCLUSIVAMENTE en el contexto proporcionado.
- Si la respuesta no está en el contexto, admítelo y no inventes.
- Cita las fuentes usando el formato [nombre_archivo].

CONTEXTO PROPORCIONADO:
{{context}}

PREGUNTA: {{question}}

RESPUESTA:"""
        
        custom_prompt = PromptTemplate(
            template=system_template,
            input_variables=["context", "question"]
        )
        
        # Crear retriever con MMR (Maximal Marginal Relevance) para reducir redundancia
        retriever = vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 5,           # Número de documentos a retornar
                "fetch_k": 20,    # Número de documentos a recuperar para MMR
                "lambda_mult": 0.5  # Balance entre relevancia y diversidad (0.5 es un buen balance)
            }
        )
        
        # Crear cadena de conversación
        chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            memory=memory,
            combine_docs_chain_kwargs={"prompt": custom_prompt},
            return_source_documents=True,
            verbose=False
        )
        
        return chain
    except Exception as e:
        st.error(f"Error al inicializar cadena de conversación: {str(e)}")
        return None


def initialize_agent(
    vector_store,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    session_id: str = None,
    chat_history: list = None,
    document_registry: dict = None
):
    """Inicializa un agente React con herramientas de búsqueda por documento.

    Crea un agente LangGraph que tiene una herramienta de retrieval por cada
    documento procesado, más un buscador general como fallback.

    Args:
        vector_store: El vector store de Chroma.
        temperature: Nivel de creatividad del modelo.
        max_tokens: Límite de tokens en la respuesta.
        session_id: ID de sesión para cargar hechos del usuario.
        chat_history: Lista de mensajes previos.
        document_registry: Dict {filename: document_card} con metadatos agénticos.

    Returns:
        El agente de LangGraph configurado, o None si falla.
    """
    try:
        if vector_store is None:
            return None

        # === 1. Inicializar el modelo ===
        credentials, project_id = get_credentials_and_project()

        if not project_id:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
            if not api_key:
                st.error(
                    "❌ No se encontraron credenciales para el modelo de chat.\\n\\n"
                    "Opción 1: Coloca un archivo JSON de credenciales de servicio en el directorio.\\n"
                    "Opción 2: Configura GOOGLE_API_KEY o VERTEX_AI_API_KEY en tu archivo .env"
                )
                return None

            llm = ChatGoogleGenerativeAI(
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-2.5-pro",
                temperature=temperature,
                max_output_tokens=max_tokens,
                api_key=api_key
            )
        else:
            llm = ChatGoogleGenerativeAI(
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-2.5-pro",
                temperature=temperature,
                max_output_tokens=max_tokens,
                vertexai=True,
                project=project_id,
                location="us-central1"
            )

        # === 2. Construir herramientas por documento ===
        tools = []

        if document_registry:
            for filename, card in document_registry.items():
                usage_guide = card.get("usage_guide", "")
                tool = create_document_tool(vector_store, filename, usage_guide)
                if tool:
                    tools.append(tool)
                    print(f"[Agent] Tool añadida: {tool.name}")

        # === 3. Herramienta de búsqueda general (fallback) ===
        general_retriever = vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 5,
                "fetch_k": 20,
                "lambda_mult": 0.5
            }
        )
        general_tool = create_retriever_tool(
            retriever=general_retriever,
            name="search_all_documents",
            description=(
                "Busca información en TODOS los documentos disponibles. "
                "Usa esta herramienta cuando la pregunta no se refiera a un "
                "documento específico o cuando las herramientas de documentos "
                "individuales no tengan la respuesta."
            ),
        )
        tools.append(general_tool)

        # === 4. Obtener hechos del usuario ===
        user_facts_section = ""
        if session_id:
            try:
                user_mem = UserMemoryManager()
                user_facts = user_mem.get_user_facts_formatted(session_id)
                if user_facts:
                    user_facts_section = f"""\n\nINFORMACIÓN CONOCIDA SOBRE EL USUARIO:
{user_facts}

Usa esta información para personalizar tus respuestas cuando sea relevante."""
            except Exception as e:
                print(f"Error cargando hechos del usuario: {e}")

        # === 5. System Prompt agéntico ===
        # Construir lista legible de herramientas para el prompt
        tool_descriptions = "\n".join(
            f"  - **{t.name}**: {t.description}" for t in tools
        )

        system_prompt = f"""Eres un asistente educativo avanzado con acceso a una biblioteca de documentos específicos.{user_facts_section}

TIENES ACCESO A LAS SIGUIENTES HERRAMIENTAS DE BÚSQUEDA:
{tool_descriptions}

TU PROCESO DE TRABAJO:
1. **Lee las descripciones** de tus herramientas disponibles.
2. **Elige la herramienta más apropiada** según la pregunta del usuario.
3. Si la pregunta se refiere a un tema cubierto por un documento específico, usa la herramienta de ese documento.
4. Si la pregunta es general o abarca varios documentos, usa "search_all_documents".
5. **Analiza los resultados** obtenidos de la herramienta.
6. **Formula tu respuesta** basándote EXCLUSIVAMENTE en la información recuperada.

INSTRUCCIONES DE RESPUESTA:
- Basa tu respuesta EXCLUSIVAMENTE en el contexto recuperado por las herramientas.
- Si la información no está disponible, admítelo y no inventes.
- Cita las fuentes usando el formato [nombre_archivo].
- Sé claro, estructurado y educativo en tus respuestas."""

        # === 6. Construir historial de mensajes ===
        messages = []
        if chat_history:
            for msg in chat_history:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg.get("content", "")))

        # === 7. Crear agente React ===
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=system_prompt,
            name="educational_rag_agent",
        )

        print(f"[Agent] Agente inicializado con {len(tools)} herramientas")
        return agent

    except Exception as e:
        st.error(f"Error al inicializar agente: {str(e)}")
        import traceback
        print(f"[Agent] Traceback: {traceback.format_exc()}")
        return None
