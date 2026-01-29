import os
import tempfile
import time
from pathlib import Path
from typing import List, Optional

import streamlit as st
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import TokenTextSplitter
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
            raise FileNotFoundError("No se encontró el archivo de credenciales JSON")
        
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        
        return storage.Client(credentials=credentials, project=credentials.project_id)
    except Exception as e:
        st.error(f"Error de autenticación con Google Cloud: {str(e)}")
        st.info("Asegúrate de tener el archivo de credenciales JSON en el directorio actual.")
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


def procesar_pdf(ruta_archivo: str) -> List:
    """Procesa un PDF desde una ruta y retorna los documentos divididos con metadatos."""
    try:
        # Cargar PDF usando PyPDFLoader
        loader = PyPDFLoader(ruta_archivo)
        documents = loader.load()

        # Dividir documentos usando TokenTextSplitter
        text_splitter = TokenTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
        )

        # Dividir y agregar metadatos con el nombre del archivo
        splits = text_splitter.split_documents(documents)
        nombre_archivo = Path(ruta_archivo).name
        for split in splits:
            if "source" not in split.metadata:
                split.metadata["source"] = nombre_archivo

        return splits
    except Exception as e:
        st.error(f"Error al procesar PDF: {str(e)}")
        return []


def initialize_vector_store(documents: List, persist_directory: str = "./chroma_db"):
    """Inicializa o actualiza el vector store de Chroma procesando documentos en lotes."""
    try:
        embeddings = get_embeddings()
        if not embeddings:
            return None
        
        # Crear directorio si no existe
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        total_docs = len(documents)
        batch_size = 5
        num_batches = (total_docs + batch_size - 1) // batch_size  # Redondeo hacia arriba
        
        # Crear barra de progreso
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Si ya existe un vector store, agregar documentos en lotes
        if st.session_state.vector_store is not None:
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
        else:
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
        
        # Configurar memoria
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer"
        )
        
        # System prompt personalizado
        system_template = """Eres un tutor universitario útil. Usa los siguientes fragmentos de contexto para responder a la pregunta. Si no sabes la respuesta, di que no está en el temario. Si el usuario pide preguntas de examen, genera preguntas desafiantes basadas en el texto.

{context}

Pregunta: {question}

Respuesta útil:"""
        
        custom_prompt = PromptTemplate(
            template=system_template,
            input_variables=["context", "question"]
        )
        
        # Crear cadena de conversación
        chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=st.session_state.vector_store.as_retriever(
                search_kwargs={"k": 5}
            ),
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

    # Selector de fuente del documento
    st.subheader("📄 Fuente del Documento")
    fuente_documento = st.radio(
        "Fuente del Documento",
        ["Subir Nuevo PDF", "Seleccionar de la Nube"],
        index=0,
        help="Elige si quieres subir un nuevo PDF o usar uno que ya esté en el bucket de Google Cloud Storage",
    )

    # Opción: Subir nuevo PDF
    if fuente_documento == "Subir Nuevo PDF":
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

    # Opción: Seleccionar desde la nube
    else:
        st.subheader("☁️ Seleccionar PDF desde la Nube")
        client = get_gcs_client()

        if client:
            try:
                bucket = client.bucket(BUCKET_NAME)
                blobs = list(bucket.list_blobs())
                pdf_files = [blob.name for blob in blobs if blob.name.lower().endswith(".pdf")]
            except Exception as e:
                pdf_files = []
                st.error(f"Error al listar archivos del bucket: {str(e)}")

            if not pdf_files:
                st.info("No hay archivos PDF disponibles en el bucket actualmente.")
            else:
                # Selectbox para elegir archivo (solo lista nombres, no descarga nada)
                selected_pdf = st.selectbox(
                    "Elige un archivo disponible",
                    options=pdf_files,
                    help="Selecciona un PDF del bucket. Debes pulsar el botón para cargarlo y procesarlo.",
                )

                # Botón para cargar y procesar
                if st.button("Cargar y Procesar este Archivo"):
                    with st.spinner("Descargando y procesando documento..."):
                        try:
                            # Descargar el archivo seleccionado a una ruta temporal
                            blob = bucket.blob(selected_pdf)
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                                blob.download_to_file(tmp_file)
                                tmp_path = tmp_file.name

                            # Ejecutar la función de procesamiento (split + embeddings con batching)
                            documents = procesar_pdf(tmp_path)
                            os.unlink(tmp_path)

                            if documents:
                                vector_store = initialize_vector_store(documents)

                                if vector_store:
                                    # Guardar en st.session_state que el archivo activo es el seleccionado
                                    st.session_state.archivo_activo = selected_pdf
                                    
                                    # Agregar a la lista de archivos procesados si no está ya
                                    if selected_pdf not in st.session_state.processed_files:
                                        st.session_state.processed_files.append(selected_pdf)
                                    
                                    # Mensaje de éxito
                                    st.success(f"✅ Archivo '{selected_pdf}' cargado y listo para chatear.")
                                    st.info(f"Se generaron {len(documents)} chunks con embeddings.")

                                    # Reinicializar la cadena de conversación si existe
                                    if st.session_state.conversation_chain:
                                        st.session_state.conversation_chain = None
                                        st.info("Reinicia el chat para usar el nuevo documento.")
                                else:
                                    st.error("Error al crear el vector store.")
                            else:
                                st.error("No se pudieron procesar los documentos del PDF.")
                        except Exception as e:
                            st.error(f"Error al descargar o procesar el archivo desde GCS: {str(e)}")
                else:
                    # Mostrar información del archivo seleccionado si hay uno activo
                    if st.session_state.archivo_activo:
                        st.info(f"📄 Archivo activo: {st.session_state.archivo_activo}")

    # Mostrar archivos procesados
    if st.session_state.processed_files:
        st.subheader("📚 Archivos Procesados")
        for file in st.session_state.processed_files:
            st.write(f"• {file}")
    
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

