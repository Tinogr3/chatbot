import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import List, Optional

import streamlit as st
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate

from google.cloud import storage
from google.oauth2 import service_account

# Cargar variables de entorno
load_dotenv()

# Configuración de la página
st.set_page_config(
    page_title="Chatbot RAG Educativo",
    page_icon="📚",
    layout="wide"
)

# Inicializar variables de sesión
if "messages" not in st.session_state:
    st.session_state.messages = []

if "vector_store" not in st.session_state:
    st.session_state.vector_store = None

if "conversation_chain" not in st.session_state:
    st.session_state.conversation_chain = None

if "processed_files" not in st.session_state:
    st.session_state.processed_files = []

if "archivo_activo" not in st.session_state:
    st.session_state.archivo_activo = None

if "modo_operacion" not in st.session_state:
    st.session_state.modo_operacion = "Nube Automático"

if "archivos_manuales" not in st.session_state:
    st.session_state.archivos_manuales = []

if "archivos_nube" not in st.session_state:
    st.session_state.archivos_nube = []

# Nombre por defecto del bucket de documentos
BUCKET_NAME = "chatbot-rag-documents"


def get_credentials_and_project():
    """Obtiene las credenciales de servicio y el project_id."""
    try:
        creds_path = None
        for file in os.listdir("."):
            if file.endswith(".json") and "client" in file.lower():
                creds_path = file
                break
        
        if not creds_path:
            return None, None
        
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return credentials, credentials.project_id
    except Exception as e:
        return None, None


def get_gcs_client():
    """Obtiene el cliente de Google Cloud Storage usando credenciales."""
    try:
        # Buscar el archivo de credenciales JSON
        creds_path = None
        for file in os.listdir("."):
            if file.endswith(".json") and "client" in file.lower():
                creds_path = file
                break
        
        if not creds_path:
            st.warning(
                "⚠️ **No se encontró el archivo de credenciales de Google Cloud**\n\n"
                "Para habilitar la funcionalidad de Google Cloud Storage, sigue estos pasos:\n\n"
                "**Opción 1: Usar archivo de credenciales JSON**\n"
                "1. Descarga tu archivo de credenciales desde Google Cloud Console\n"
                "2. Coloca el archivo .json en el directorio raíz del proyecto (donde está app.py)\n"
                "3. El archivo debe contener 'client' en su nombre (ej: client_secret.json)\n\n"
                "**Opción 2: Usar variables de entorno**\n"
                "1. Configura la variable GOOGLE_APPLICATION_CREDENTIALS en tu .env\n"
                "2. Ejemplo: `GOOGLE_APPLICATION_CREDENTIALS=/ruta/a/credenciales.json`\n\n"
                "**Nota:** Sin credenciales, el chatbot seguirá funcionando en modo local sin acceso a GCS."
            )
            return None
        
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        
        return storage.Client(credentials=credentials, project=credentials.project_id)
    except FileNotFoundError as e:
        st.warning(
            f"⚠️ **Archivo de credenciales no encontrado: {str(e)}**\n\n"
            "Asegúrate de que el archivo existe en la ruta especificada."
        )
        return None
    except Exception as e:
        st.warning(
            f"⚠️ **Error de autenticación con Google Cloud**\n\n"
            f"Detalles: {str(e)}\n\n"
            "Verifica que el archivo de credenciales sea válido y tenga los permisos necesarios."
        )
        return None


@st.cache_resource
def get_embeddings():
    """Inicializa el modelo de embeddings de Google Generative AI usando Vertex AI."""
    try:
        credentials, project_id = get_credentials_and_project()
        
        if not project_id:
            # Si no hay credenciales de servicio, intentar con API key
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if api_key:
                return GoogleGenerativeAIEmbeddings(
                    model="text-embedding-004",
                    api_key=api_key
                )
            else:
                st.error(
                    "❌ No se encontraron credenciales.\n\n"
                    "Opción 1: Coloca un archivo JSON de credenciales de servicio en el directorio.\n"
                    "Opción 2: Configura GOOGLE_API_KEY o GEMINI_API_KEY en tu archivo .env"
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


def procesar_todos_pdfs_nube(bucket_name: str = BUCKET_NAME) -> tuple[List, List[str]]:
    """Descarga y procesa todos los PDFs del bucket de GCS.
    
    Returns:
        Tuple con (lista de documentos procesados, lista de nombres de archivos)
    """
    client = get_gcs_client()
    if not client:
        return [], []
    
    try:
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs())
        pdf_files = [blob.name for blob in blobs if blob.name.lower().endswith(".pdf")]
        
        if not pdf_files:
            return [], []
        
        all_documents = []
        processed_filenames = []
        
        with st.spinner(f"Descargando y procesando {len(pdf_files)} archivos del bucket..."):
            for pdf_name in pdf_files:
                try:
                    blob = bucket.blob(pdf_name)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        blob.download_to_file(tmp_file)
                        tmp_path = tmp_file.name
                    
                    documents = procesar_pdf(tmp_path)
                    os.unlink(tmp_path)
                    
                    if documents:
                        all_documents.extend(documents)
                        processed_filenames.append(pdf_name)
                except Exception as e:
                    st.warning(f"Error al procesar {pdf_name}: {str(e)}")
                    continue
        
        return all_documents, processed_filenames
    except Exception as e:
        st.error(f"Error al listar o descargar archivos del bucket: {str(e)}")
        return [], []


def upload_to_gcs(file_content: bytes, filename: str, bucket_name: str = BUCKET_NAME) -> Optional[str]:
    """Sube un archivo a Google Cloud Storage."""
    client = get_gcs_client()
    if not client:
        return None
    
    try:
        # Crear bucket si no existe
        try:
            bucket = client.bucket(bucket_name)
            bucket.create()
        except Exception:
            bucket = client.bucket(bucket_name)
        
        # Subir archivo
        blob = bucket.blob(filename)
        blob.upload_from_string(file_content, content_type="application/pdf")
        
        return f"gs://{bucket_name}/{filename}"
    except Exception as e:
        st.error(f"Error al subir archivo a GCS: {str(e)}")
        return None


def limpiar_texto(texto: str) -> str:
    """Limpia el texto eliminando espacios excesivos y caracteres extraños."""
    if not texto:
        return texto
    
    # Eliminar espacios múltiples y reemplazar por uno solo
    texto = re.sub(r'\s+', ' ', texto)
    
    # Eliminar espacios al inicio y final
    texto = texto.strip()
    
    # Eliminar caracteres de control y caracteres extraños (mantener solo imprimibles)
    texto = ''.join(char for char in texto if char.isprintable() or char in '\n\t')
    
    # Normalizar saltos de línea múltiples
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    
    return texto


def procesar_pdf(ruta_archivo: str) -> List:
    """Procesa un PDF desde una ruta y retorna los documentos divididos con metadatos."""
    try:
        # Cargar PDF usando PyPDFLoader
        loader = PyPDFLoader(ruta_archivo)
        documents = loader.load()

        # Limpiar el texto de cada documento antes de dividir
        for doc in documents:
            if doc.page_content:
                doc.page_content = limpiar_texto(doc.page_content)

        # Dividir documentos usando RecursiveCharacterTextSplitter con separadores lógicos
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=[
                "\n\n",  # Saltos de párrafo (prioridad más alta)
                "\n",    # Saltos de línea
                ". ",    # Puntos seguidos de espacio
                "! ",    # Signos de exclamación
                "? ",    # Signos de interrogación
                "; ",    # Punto y coma
                ", ",    # Comas
                " ",     # Espacios
                ""       # Caracteres individuales (último recurso)
            ],
            length_function=len,
        )

        # Dividir documentos (RecursiveCharacterTextSplitter conserva automáticamente los metadatos)
        splits = text_splitter.split_documents(documents)
        
        # Asegurar que los metadatos se conserven correctamente en cada chunk
        nombre_archivo = Path(ruta_archivo).name
        for split in splits:
            # Asegurar que siempre tengamos el nombre del archivo como fuente
            split.metadata["source"] = nombre_archivo
            
            # El número de página debería estar ya en los metadatos del documento original
            # PyPDFLoader incluye 'page' en los metadatos, y RecursiveCharacterTextSplitter
            # los conserva automáticamente. Si no está, intentamos mantenerlo del documento original.
            if "page" not in split.metadata:
                # Buscar en los documentos originales para encontrar la página correspondiente
                # Esto es una medida de seguridad por si acaso
                for doc in documents:
                    if doc.page_content and doc.page_content in split.page_content:
                        if "page" in doc.metadata:
                            split.metadata["page"] = doc.metadata["page"]
                        break

        return splits
    except Exception as e:
        st.error(f"Error al procesar PDF: {str(e)}")
        return []


def initialize_vector_store(documents: List, persist_directory: str = "/tmp/chroma_db", crear_nuevo: bool = False):
    """Inicializa o actualiza el vector store de Chroma procesando documentos en lotes.
    
    Args:
        documents: Lista de documentos a procesar
        persist_directory: Directorio donde persistir la base de datos
        crear_nuevo: Si True, crea un nuevo vector store (limpia el anterior). Si False, agrega a uno existente.
    """
    try:
        embeddings = get_embeddings()
        if not embeddings:
            return None
        
        # Crear directorio si no existe con permisos explícitos
        Path(persist_directory).mkdir(parents=True, exist_ok=True, mode=0o755)
        
        total_docs = len(documents)
        if total_docs == 0:
            return st.session_state.vector_store
        
        batch_size = 5
        num_batches = (total_docs + batch_size - 1) // batch_size  # Redondeo hacia arriba
        
        # Crear barra de progreso
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Si se debe crear nuevo o no existe vector store, crear uno nuevo
        if crear_nuevo or st.session_state.vector_store is None:
            # Limpiar el directorio si se crea nuevo
            if crear_nuevo and Path(persist_directory).exists():
                try:
                    shutil.rmtree(persist_directory)
                    Path(persist_directory).mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
            
            # Crear nuevo vector store con el primer lote
            first_batch = documents[0:min(batch_size, total_docs)]
            st.session_state.vector_store = Chroma.from_documents(
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
                st.session_state.vector_store.add_documents(batch)
                
                # Esperar 2 segundos antes del siguiente lote (excepto en el último)
                if i + batch_size < total_docs:
                    time.sleep(2)
        else:
            # Agregar documentos al vector store existente en lotes
            for i in range(0, total_docs, batch_size):
                batch = documents[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                # Actualizar barra de progreso
                progress = (i + len(batch)) / total_docs
                progress_bar.progress(progress)
                status_text.text(f"Procesando lote {batch_num}/{num_batches} ({len(batch)} documentos)...")
                
                # Agregar lote al vector store
                st.session_state.vector_store.add_documents(batch)
                
                # Esperar 2 segundos antes del siguiente lote (excepto en el último)
                if i + batch_size < total_docs:
                    time.sleep(2)
        
        # Completar barra de progreso
        progress_bar.progress(1.0)
        status_text.text(f"✅ Procesados {total_docs} documentos en {num_batches} lotes.")
        time.sleep(0.5)  # Pequeña pausa para mostrar el mensaje final
        status_text.empty()
        progress_bar.empty()
        
        return st.session_state.vector_store
    except Exception as e:
        st.error(f"Error al inicializar vector store: {str(e)}")
        return None


def initialize_conversation_chain(temperature: float = 0.7, max_tokens: int = 2048):
    """Inicializa la cadena de conversación con memoria."""
    try:
        if st.session_state.vector_store is None:
            return None
        
        # Inicializar el modelo de chat
        credentials, project_id = get_credentials_and_project()
        
        if not project_id:
            # Si no hay credenciales de servicio, intentar con API key
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if not api_key:
                st.error(
                    "❌ No se encontraron credenciales para el modelo de chat.\n\n"
                    "Opción 1: Coloca un archivo JSON de credenciales de servicio en el directorio.\n"
                    "Opción 2: Configura GOOGLE_API_KEY o GEMINI_API_KEY en tu archivo .env"
                )
                return None
            
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=temperature,
                max_output_tokens=max_tokens,
                api_key=api_key
            )
        else:
            # Usar Vertex AI con credenciales de servicio
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
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
        
        # System prompt personalizado mejorado
        system_template = """Eres un tutor universitario experto y preciso. Sigue estas instrucciones estrictamente:

INSTRUCCIONES:
1. ANTES de responder, piensa paso a paso:
   - Analiza la pregunta cuidadosamente
   - Revisa el contexto proporcionado
   - Identifica qué información es relevante
   - Determina si tienes suficiente información para responder

2. AL RESPONDER:
   - Cita EXPLÍCITAMENTE el nombre del documento (archivo) del que obtienes cada pieza de información
   - Usa el formato: "Según [nombre del archivo]..." o "En [nombre del archivo] se menciona que..."
   - Si mencionas información de múltiples documentos, cita cada uno
   - Sé preciso y basado únicamente en el contexto proporcionado

3. SI NO TIENES INFORMACIÓN SUFICIENTE:
   - Di claramente: "No tengo información suficiente en los documentos proporcionados para responder a esta pregunta."
   - NO inventes, NO especules, NO uses conocimiento general
   - Si la pregunta es sobre algo que no está en el contexto, sé honesto al respecto

4. SI EL USUARIO PIDE PREGUNTAS DE EXAMEN:
   - Genera preguntas desafiantes basadas ÚNICAMENTE en el texto proporcionado
   - Cita el documento de donde proviene cada pregunta

CONTEXTO PROPORCIONADO:
{context}

PREGUNTA DEL USUARIO:
{question}

RESPUESTA (piensa paso a paso, cita las fuentes, sé preciso):"""
        
        custom_prompt = PromptTemplate(
            template=system_template,
            input_variables=["context", "question"]
        )
        
        # Crear retriever con MMR (Maximal Marginal Relevance) para reducir redundancia
        retriever = st.session_state.vector_store.as_retriever(
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


# Sidebar de configuración
with st.sidebar:
    st.header("⚙️ Configuración")

    # Selector de modo de operación
    st.subheader("🔀 Modo de Operación")
    modo_anterior = st.session_state.modo_operacion
    modo_operacion = st.radio(
        "Modo de Operación",
        ["Nube Automático", "Manual (Upload)", "Híbrido (Todo)"],
        index=["Nube Automático", "Manual (Upload)", "Híbrido (Todo)"].index(st.session_state.modo_operacion),
        help="Elige cómo quieres gestionar los documentos del chatbot"
    )
    
    # Si cambió el modo, limpiar el vector store y reinicializar
    if modo_operacion != modo_anterior:
        st.session_state.modo_operacion = modo_operacion
        st.session_state.vector_store = None
        st.session_state.conversation_chain = None
        st.session_state.messages = []
        st.session_state.archivos_manuales = []
        st.session_state.archivos_nube = []
        st.session_state.processed_files = []
        st.session_state.archivo_activo = None
        st.rerun()

    # Lógica según el modo seleccionado
    if modo_operacion == "Nube Automático":
        st.subheader("☁️ Modo Nube Automático")
        st.info("Este modo procesa automáticamente todos los PDFs del bucket.")
        
        if st.button("🔄 Cargar Todos los PDFs del Bucket"):
            with st.spinner("Descargando y procesando todos los PDFs..."):
                documents, filenames = procesar_todos_pdfs_nube()
                
                if documents:
                    # Crear nuevo vector store (limpiar cualquier documento manual anterior)
                    vector_store = initialize_vector_store(documents, crear_nuevo=True)
                    
                    if vector_store:
                        st.session_state.archivos_nube = filenames
                        st.session_state.processed_files = filenames
                        st.session_state.archivo_activo = f"{len(filenames)} archivos de la nube"
                        
                        st.success(f"✅ {len(filenames)} archivos cargados desde la nube.")
                        st.info(f"Se generaron {len(documents)} chunks con embeddings.")
                        
                        # Reinicializar la cadena de conversación
                        st.session_state.conversation_chain = None
                        st.rerun()
                    else:
                        st.error("Error al crear el vector store.")
                else:
                    st.warning("No se encontraron PDFs en el bucket o hubo errores al procesarlos.")
        
        # Mostrar archivos de la nube procesados
        if st.session_state.archivos_nube:
            st.subheader("📚 Archivos de la Nube")
            for file in st.session_state.archivos_nube:
                st.write(f"☁️ {file}")
    
    elif modo_operacion == "Manual (Upload)":
        st.subheader("📤 Modo Manual (Upload)")
        st.info("Solo se consideran los archivos que subas manualmente en esta sesión.")
        
        uploaded_file = st.file_uploader(
            "Selecciona un archivo PDF",
            type=["pdf"],
            help="Sube un archivo PDF para procesarlo y agregarlo al conocimiento del chatbot",
        )

        if uploaded_file is not None:
            if st.button("Procesar y Subir PDF"):
                with st.spinner("Procesando documento..."):
                    # Leer contenido del archivo
                    file_content = uploaded_file.read()
                    filename = uploaded_file.name

                    # Subir a Google Cloud Storage (opcional, pero lo mantenemos)
                    st.info("Subiendo archivo a Google Cloud Storage...")
                    gcs_path = upload_to_gcs(file_content, filename)

                    if gcs_path:
                        st.success(f"Archivo subido a: {gcs_path}")

                        # Guardar en un archivo temporal y procesar
                        st.info("Procesando PDF y generando embeddings...")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                            tmp_file.write(file_content)
                            tmp_path = tmp_file.name

                        documents = procesar_pdf(tmp_path)
                        os.unlink(tmp_path)

                        if documents:
                            # Si es el primer archivo manual, crear nuevo vector store
                            crear_nuevo = len(st.session_state.archivos_manuales) == 0
                            
                            # Inicializar o actualizar vector store
                            vector_store = initialize_vector_store(documents, crear_nuevo=crear_nuevo)

                            if vector_store:
                                # Guardar en st.session_state que el archivo activo es el procesado
                                st.session_state.archivo_activo = filename
                                
                                # Agregar a la lista de archivos manuales
                                if filename not in st.session_state.archivos_manuales:
                                    st.session_state.archivos_manuales.append(filename)
                                
                                # Actualizar lista de archivos procesados
                                st.session_state.processed_files = st.session_state.archivos_manuales.copy()
                                
                                st.success(f"✅ Archivo '{filename}' cargado y listo para chatear.")
                                st.info(f"Se generaron {len(documents)} chunks con embeddings.")

                                # Reinicializar la cadena de conversación si existe
                                if st.session_state.conversation_chain:
                                    st.session_state.conversation_chain = None
                                    st.info("Reinicia el chat para usar el nuevo documento.")
                            else:
                                st.error("Error al crear el vector store.")
                        else:
                            st.error("No se pudieron procesar los documentos del PDF.")
                    else:
                        st.error("Error al subir el archivo a Google Cloud Storage.")
        
        # Mostrar archivos manuales procesados
        if st.session_state.archivos_manuales:
            st.subheader("📚 Archivos Manuales")
            for file in st.session_state.archivos_manuales:
                st.write(f"📄 {file}")
    
    else:  # Modo Híbrido
        st.subheader("🔄 Modo Híbrido (Todo)")
        st.info("Combina documentos de la nube con los que subas manualmente.")
        
        # Sección para cargar desde la nube
        st.markdown("#### ☁️ Documentos de la Nube")
        if st.button("🔄 Cargar Todos los PDFs del Bucket"):
            with st.spinner("Descargando y procesando todos los PDFs..."):
                documents, filenames = procesar_todos_pdfs_nube()
                
                if documents:
                    # Crear nuevo vector store solo si no hay nada
                    crear_nuevo = st.session_state.vector_store is None
                    
                    vector_store = initialize_vector_store(documents, crear_nuevo=crear_nuevo)
                    
                    if vector_store:
                        st.session_state.archivos_nube = filenames
                        st.success(f"✅ {len(filenames)} archivos cargados desde la nube.")
                        st.info(f"Se generaron {len(documents)} chunks con embeddings.")
                        
                        # Actualizar lista de archivos procesados
                        st.session_state.processed_files = st.session_state.archivos_nube.copy() + st.session_state.archivos_manuales.copy()
                        
                        # Reinicializar la cadena de conversación
                        st.session_state.conversation_chain = None
                        st.rerun()
                    else:
                        st.error("Error al crear el vector store.")
                else:
                    st.warning("No se encontraron PDFs en el bucket o hubo errores al procesarlos.")
        
        # Mostrar archivos de la nube
        if st.session_state.archivos_nube:
            st.write("**Archivos de la nube:**")
            for file in st.session_state.archivos_nube:
                st.write(f"☁️ {file}")
        
        st.divider()
        
        # Sección para subir manualmente
        st.markdown("#### 📤 Subir Archivo Manual")
        uploaded_file = st.file_uploader(
            "Selecciona un archivo PDF",
            type=["pdf"],
            help="Sube un archivo PDF para procesarlo y agregarlo al conocimiento del chatbot",
            key="hybrid_upload"
        )

        if uploaded_file is not None:
            if st.button("Procesar y Subir PDF"):
                with st.spinner("Procesando documento..."):
                    # Leer contenido del archivo
                    file_content = uploaded_file.read()
                    filename = uploaded_file.name

                    # Subir a Google Cloud Storage
                    st.info("Subiendo archivo a Google Cloud Storage...")
                    gcs_path = upload_to_gcs(file_content, filename)

                    if gcs_path:
                        st.success(f"Archivo subido a: {gcs_path}")

                        # Guardar en un archivo temporal y procesar
                        st.info("Procesando PDF y generando embeddings...")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                            tmp_file.write(file_content)
                            tmp_path = tmp_file.name

                        documents = procesar_pdf(tmp_path)
                        os.unlink(tmp_path)

                        if documents:
                            # Agregar al vector store existente (no crear nuevo)
                            vector_store = initialize_vector_store(documents, crear_nuevo=False)

                            if vector_store:
                                # Agregar a la lista de archivos manuales
                                if filename not in st.session_state.archivos_manuales:
                                    st.session_state.archivos_manuales.append(filename)
                                
                                # Actualizar lista de archivos procesados
                                st.session_state.processed_files = st.session_state.archivos_nube.copy() + st.session_state.archivos_manuales.copy()
                                
                                st.success(f"✅ Archivo '{filename}' cargado y listo para chatear.")
                                st.info(f"Se generaron {len(documents)} chunks con embeddings.")

                                # Reinicializar la cadena de conversación si existe
                                if st.session_state.conversation_chain:
                                    st.session_state.conversation_chain = None
                                    st.info("Reinicia el chat para usar el nuevo documento.")
                            else:
                                st.error("Error al crear el vector store.")
                        else:
                            st.error("No se pudieron procesar los documentos del PDF.")
                    else:
                        st.error("Error al subir el archivo a Google Cloud Storage.")
        
        # Mostrar archivos manuales
        if st.session_state.archivos_manuales:
            st.write("**Archivos manuales:**")
            for file in st.session_state.archivos_manuales:
                st.write(f"📄 {file}")
        st.subheader("📄 Subir Documentos PDF")
        uploaded_file = st.file_uploader(
            "Selecciona un archivo PDF",
            type=["pdf"],
            help="Sube un archivo PDF para procesarlo y agregarlo al conocimiento del chatbot",
        )

        if uploaded_file is not None:
            if st.button("Procesar y Subir PDF"):
                with st.spinner("Procesando documento..."):
                    # Leer contenido del archivo
                    file_content = uploaded_file.read()
                    filename = uploaded_file.name

                    # Subir a Google Cloud Storage
                    st.info("Subiendo archivo a Google Cloud Storage...")
                    gcs_path = upload_to_gcs(file_content, filename)

                    if gcs_path:
                        st.success(f"Archivo subido a: {gcs_path}")

                        # Guardar en un archivo temporal y procesar
                        st.info("Procesando PDF y generando embeddings...")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                            tmp_file.write(file_content)
                            tmp_path = tmp_file.name

                        documents = procesar_pdf(tmp_path)
                        os.unlink(tmp_path)

                        if documents:
                            # Inicializar o actualizar vector store
                            vector_store = initialize_vector_store(documents)

                            if vector_store:
                                # Guardar en st.session_state que el archivo activo es el procesado
                                st.session_state.archivo_activo = filename
                                
                                # Agregar a la lista de archivos procesados si no está ya
                                if filename not in st.session_state.processed_files:
                                    st.session_state.processed_files.append(filename)
                                
                                st.success(f"✅ Archivo '{filename}' cargado y listo para chatear.")
                                st.info(f"Se generaron {len(documents)} chunks con embeddings.")

                                # Reinicializar la cadena de conversación si existe
                                if st.session_state.conversation_chain:
                                    st.session_state.conversation_chain = None
                                    st.info("Reinicia el chat para usar el nuevo documento.")
                            else:
                                st.error("Error al crear el vector store.")
                        else:
                            st.error("No se pudieron procesar los documentos del PDF.")
                    else:
                        st.error("Error al subir el archivo a Google Cloud Storage.")
    
    st.divider()
    
    # Botón para limpiar memoria
    st.subheader("🧹 Gestión de Sesión")
    if st.button("🗑️ Limpiar Memoria", help="Borra el historial del chat y el vector store para empezar de cero"):
        # Limpiar el historial de mensajes
        st.session_state.messages = []
        
        # Limpiar el vector store y la cadena de conversación
        st.session_state.vector_store = None
        st.session_state.conversation_chain = None
        
        # Limpiar archivos procesados
        st.session_state.processed_files = []
        st.session_state.archivos_manuales = []
        st.session_state.archivos_nube = []
        st.session_state.archivo_activo = None
        
        # Intentar limpiar el directorio de Chroma si existe
        try:
            persist_directory = "/tmp/chroma_db"
            if Path(persist_directory).exists():
                shutil.rmtree(persist_directory)
        except Exception as e:
            pass  # Silenciar error si no se puede eliminar
        
        st.success("✅ Memoria limpiada exitosamente. Puedes comenzar de cero.")
        st.rerun()
    
    st.divider()
    
    # Sliders de parametrización
    st.subheader("🎛️ Parámetros del Modelo")
    
    temperature = st.slider(
        "Nivel de Creatividad (Temperature)",
        min_value=0.0,
        max_value=2.0,
        value=0.7,
        step=0.1,
        help="Valores más altos hacen el modelo más creativo, valores más bajos lo hacen más determinista"
    )
    
    max_tokens = st.slider(
        "Límite de Tokens",
        min_value=256,
        max_value=65535,
        value=2048,
        step=256,
        help="Número máximo de tokens en la respuesta"
    )
    
    # Botón para aplicar cambios
    if st.button("🔄 Aplicar Parámetros"):
        if st.session_state.vector_store:
            with st.spinner("Reinicializando modelo con nuevos parámetros..."):
                st.session_state.conversation_chain = initialize_conversation_chain(
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                if st.session_state.conversation_chain:
                    st.success("Parámetros aplicados correctamente!")
                else:
                    st.error("Error al aplicar parámetros.")
        else:
            st.warning("Primero debes procesar al menos un documento PDF.")


# Área principal del chat
st.title("📚 Chatbot RAG Educativo")
st.markdown("---")

# Verificar si hay documentos procesados
if st.session_state.vector_store is None:
    st.warning("⚠️ Por favor, sube y procesa al menos un documento PDF en la barra lateral para comenzar.")
else:
    # Inicializar cadena de conversación si no existe
    if st.session_state.conversation_chain is None:
        with st.spinner("Inicializando chatbot..."):
            st.session_state.conversation_chain = initialize_conversation_chain(
                temperature=temperature,
                max_tokens=max_tokens
            )
    
    if st.session_state.conversation_chain:
        # Mostrar historial de mensajes
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if "sources" in message and message["sources"]:
                    with st.expander("📄 Fuentes utilizadas"):
                        for source in message["sources"]:
                            st.write(f"• {source}")
        
        # Input del usuario
        if prompt := st.chat_input("Escribe tu pregunta aquí..."):
            # Agregar mensaje del usuario al historial
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generar respuesta
            with st.chat_message("assistant"):
                with st.spinner("Pensando..."):
                    try:
                        # Ejecutar la cadena de conversación
                        result = st.session_state.conversation_chain.invoke({
                            "question": prompt
                        })
                        
                        answer = result.get("answer", "No se pudo generar una respuesta.")
                        source_documents = result.get("source_documents", [])
                        
                        # Mostrar respuesta
                        st.markdown(answer)
                        
                        # Mostrar fuentes si están disponibles
                        if source_documents:
                            sources = list(set([
                                doc.metadata.get("source", "Desconocido")
                                for doc in source_documents
                            ]))
                            with st.expander("📄 Fuentes utilizadas"):
                                for source in sources:
                                    st.write(f"• {source}")
                            
                            # Agregar respuesta al historial con fuentes
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": answer,
                                "sources": sources
                            })
                        else:
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": answer
                            })
                    except Exception as e:
                        error_msg = f"Error al generar respuesta: {str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": error_msg
                        })
    else:
        st.error("Error al inicializar la cadena de conversación. Verifica la configuración.")

# Footer
st.markdown("---")
st.caption("💡 Tip: Puedes pedirle al chatbot que genere preguntas tipo test sobre los documentos subidos.")

