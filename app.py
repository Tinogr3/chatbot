"""
Aplicación principal de Streamlit - Chatbot RAG Educativo
Interfaz de usuario que coordina los módulos de configuración, RAG y GCS.
"""
import os
import tempfile
import uuid

import streamlit as st

# Importar el gestor de historial de chat
from chat_manager import ChatHistoryManager
from user_memory import UserMemoryManager

# Importar funciones de los módulos
from config import BUCKET_NAME
from rag_engine import (
    initialize_vector_store,
    initialize_conversation_chain,
    procesar_pdf
)
from gcs_utils import (
    procesar_todos_pdfs_nube,
    upload_to_gcs
)
from media_processor import (
    process_video,
    is_youtube_url,
    extract_video_id,
    get_youtube_embed_url,
    format_timestamp
)
from router import (
    route_query,
    get_direct_response,
    get_summary_response,
    LearningFlowManager,
    QueryCategory
)

# Configuración de la página
st.set_page_config(
    page_title="Chatbot RAG Educativo",
    page_icon="📚",
    layout="wide"
)

# Inicializar gestor de historial de chat y memoria de usuario
chat_manager = ChatHistoryManager()
user_memory = UserMemoryManager()

# Verificar si el usuario ya inició sesión
if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def show_welcome_screen():
    """Muestra la pantalla de bienvenida para ingresar el nombre de usuario."""
    st.title("📚 Bienvenido al Chatbot RAG Educativo")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        ### 👋 ¡Hola!
        
        Para comenzar, ingresa tu **nombre de usuario** o **ID de sesión**.
        
        Esto nos permitirá:
        - 💾 Guardar tu historial de conversaciones
        - 🧠 Recordar información sobre ti
        - 📊 Continuar donde lo dejaste
        """)
        
        st.markdown("")
        
        with st.form("login_form"):
            username = st.text_input(
                "Nombre de Usuario / ID de Sesión",
                placeholder="Ej: juan_perez, mi_sesion_123",
                help="Usa el mismo nombre para recuperar tu historial en futuras sesiones"
            )
            
            submit = st.form_submit_button("🚀 Comenzar", use_container_width=True)
            
            if submit:
                if username and username.strip():
                    # Limpiar y normalizar el nombre de usuario
                    clean_username = username.strip().lower().replace(" ", "_")
                    st.session_state.session_id = clean_username
                    st.session_state.authenticated = True
                    
                    # Cargar historial existente
                    st.session_state.messages = chat_manager.get_history(clean_username)
                    
                    # Cargar hechos del usuario
                    user_facts = user_memory.get_user_facts(clean_username)
                    if user_facts:
                        st.success(f"¡Bienvenido de nuevo! Se cargaron {len(user_facts)} datos sobre ti.")
                    else:
                        st.success(f"¡Bienvenido, {username}! Se creó una nueva sesión.")
                    
                    st.rerun()
                else:
                    st.error("Por favor, ingresa un nombre de usuario válido.")
        
        st.markdown("")
        st.info("💡 **Tip:** Usa siempre el mismo nombre para mantener tu historial y preferencias.")


# Si no está autenticado, mostrar pantalla de bienvenida
if not st.session_state.authenticated:
    show_welcome_screen()
    st.stop()

# A partir de aquí, el usuario está autenticado
# Inicializar variables de sesión
if "messages" not in st.session_state:
    st.session_state.messages = chat_manager.get_history(st.session_state.session_id)

if "vector_store" not in st.session_state:
    # Intentar cargar base de datos existente de ChromaDB
    st.session_state.vector_store = initialize_vector_store()

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

if "videos_procesados" not in st.session_state:
    st.session_state.videos_procesados = []

# Variables para modo aprendizaje
if "learning_mode" not in st.session_state:
    st.session_state.learning_mode = False

if "learning_topic" not in st.session_state:
    st.session_state.learning_topic = None

if "last_learning_content" not in st.session_state:
    st.session_state.last_learning_content = None


# Sidebar de configuración
with st.sidebar:
    # Mostrar usuario actual y opción de cerrar sesión
    st.markdown(f"👤 **Usuario:** `{st.session_state.session_id}`")
    if st.button("🚪 Cerrar Sesión", help="Cierra sesión para cambiar de usuario"):
        st.session_state.session_id = None
        st.session_state.authenticated = False
        st.session_state.messages = []
        st.session_state.vector_store = None
        st.session_state.conversation_chain = None
        st.rerun()
    
    st.divider()
    
    # Sección: Memoria del Agente
    with st.expander("🧠 Lo que sé de ti", expanded=False):
        user_facts = user_memory.get_user_facts(st.session_state.session_id)
        
        if user_facts:
            # Agrupar hechos por tipo
            facts_by_type = {}
            type_icons = {
                "nombre": "👤",
                "trabajo": "💼",
                "educacion": "🎓",
                "stack_tecnologico": "💻",
                "preferencias": "⭐",
                "ubicacion": "📍",
                "otro": "📝"
            }
            type_labels = {
                "nombre": "Nombre",
                "trabajo": "Trabajo",
                "educacion": "Educación",
                "stack_tecnologico": "Stack",
                "preferencias": "Intereses",
                "ubicacion": "Ubicación",
                "otro": "Otros"
            }
            
            for fact in user_facts:
                tipo = fact["tipo"]
                if tipo not in facts_by_type:
                    facts_by_type[tipo] = []
                facts_by_type[tipo].append(fact["valor"])
            
            # Mostrar como tags/chips
            for tipo, valores in facts_by_type.items():
                icon = type_icons.get(tipo, "📝")
                label = type_labels.get(tipo, tipo.capitalize())
                st.markdown(f"**{icon} {label}:**")
                
                # Mostrar valores como badges inline
                tags_html = " ".join([
                    f'<span style="background-color: #262730; padding: 2px 8px; border-radius: 12px; margin: 2px; display: inline-block; font-size: 0.85em;">{v}</span>'
                    for v in valores
                ])
                st.markdown(tags_html, unsafe_allow_html=True)
            
            st.markdown("")
            
            # Botón para borrar memoria
            if st.button("🗑️ Olvídame", help="Borra toda la información que sé sobre ti", key="forget_me"):
                deleted = user_memory.delete_user_facts(st.session_state.session_id)
                st.success(f"✅ Se eliminaron {deleted} datos sobre ti.")
                st.rerun()
        else:
            st.caption("Aún no sé nada sobre ti. A medida que conversemos, iré aprendiendo.")
    
    st.divider()
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
        # Limpiar historial en memoria y en base de datos
        chat_manager.delete_history(st.session_state.session_id)
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
                    # Crear nuevo vector store (sin pasar existing_vector_store)
                    vector_store = initialize_vector_store(documents, existing_vector_store=None)
                    
                    if vector_store:
                        st.session_state.vector_store = vector_store
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
                            existing_vs = None if len(st.session_state.archivos_manuales) == 0 else st.session_state.vector_store
                            
                            # Inicializar o actualizar vector store
                            vector_store = initialize_vector_store(documents, existing_vector_store=existing_vs)

                            if vector_store:
                                st.session_state.vector_store = vector_store
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
                    # Agregar al vector store existente o crear nuevo
                    existing_vs = st.session_state.vector_store
                    vector_store = initialize_vector_store(documents, existing_vector_store=existing_vs)
                    
                    if vector_store:
                        st.session_state.vector_store = vector_store
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
                            # Agregar al vector store existente
                            vector_store = initialize_vector_store(documents, existing_vector_store=st.session_state.vector_store)

                            if vector_store:
                                st.session_state.vector_store = vector_store
                                
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
    
    st.divider()
    
    # Sección de Videos de YouTube (disponible en todos los modos)
    st.subheader("🎬 Videos de YouTube")
    st.info("Añade videos de YouTube para extraer conocimiento de sus transcripciones.")
    
    youtube_url = st.text_input(
        "URL del video de YouTube",
        placeholder="https://www.youtube.com/watch?v=...",
        help="Pega la URL de un video de YouTube para extraer su transcripción"
    )
    
    if youtube_url:
        if st.button("🎥 Procesar Video"):
            if is_youtube_url(youtube_url):
                with st.spinner("Extrayendo transcripción del video..."):
                    try:
                        documents = process_video(youtube_url)
                        
                        if documents:
                            # Agregar al vector store
                            vector_store = initialize_vector_store(
                                documents, 
                                existing_vector_store=st.session_state.vector_store
                            )
                            
                            if vector_store:
                                st.session_state.vector_store = vector_store
                                
                                # Agregar a la lista de videos procesados
                                video_id = extract_video_id(youtube_url)
                                if youtube_url not in st.session_state.videos_procesados:
                                    st.session_state.videos_procesados.append(youtube_url)
                                
                                st.success(f"✅ Video procesado correctamente.")
                                st.info(f"Se generaron {len(documents)} chunks con timestamps.")
                                
                                # Reinicializar la cadena de conversación
                                st.session_state.conversation_chain = None
                            else:
                                st.error("Error al agregar video al vector store.")
                        else:
                            st.warning("No se pudo extraer contenido del video.")
                    except ValueError as e:
                        st.error(f"❌ {str(e)}")
                    except Exception as e:
                        st.error(f"❌ Error al procesar video: {str(e)}")
            else:
                st.error("Por favor, introduce una URL válida de YouTube.")
    
    # Mostrar videos procesados
    if st.session_state.videos_procesados:
        st.write("**Videos procesados:**")
        for video_url in st.session_state.videos_procesados:
            video_id = extract_video_id(video_url)
            st.write(f"🎬 `{video_id}`")
    
    st.divider()
    
    # Botón para limpiar memoria
    st.subheader("🧹 Gestión de Sesión")
    if st.button("🗑️ Limpiar Memoria", help="Borra el historial del chat y el vector store para empezar de cero"):
        # Limpiar el historial de mensajes en base de datos
        chat_manager.delete_history(st.session_state.session_id)
        st.session_state.messages = []
        
        # Limpiar el vector store y la cadena de conversación
        st.session_state.vector_store = None
        st.session_state.conversation_chain = None
        
        # Limpiar archivos procesados
        st.session_state.processed_files = []
        st.session_state.archivos_manuales = []
        st.session_state.archivos_nube = []
        st.session_state.videos_procesados = []
        st.session_state.archivo_activo = None
        
        # Nota: El historial se elimina de la base de datos SQLite
        
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
        value=65535,
        step=256,
        help="Número máximo de tokens en la respuesta"
    )
    
    # Botón para aplicar cambios
    if st.button("🔄 Aplicar Parámetros"):
        if st.session_state.vector_store:
            with st.spinner("Reinicializando modelo con nuevos parámetros..."):
                st.session_state.conversation_chain = initialize_conversation_chain(
                    vector_store=st.session_state.vector_store,
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
                vector_store=st.session_state.vector_store,
                temperature=temperature,
                max_tokens=max_tokens,
                session_id=st.session_state.session_id
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
        
        # Mostrar indicador de modo aprendizaje si está activo
        if st.session_state.learning_mode:
            st.info("🎓 **Modo Aprendizaje activo** - Responde las preguntas para continuar. Escribe 'salir' para terminar.")
        
        # Input del usuario
        if prompt := st.chat_input("Escribe tu pregunta aquí..."):
            # Agregar mensaje del usuario al historial y persistir
            st.session_state.messages.append({"role": "user", "content": prompt})
            chat_manager.save_message(st.session_state.session_id, "user", prompt)
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generar respuesta
            with st.chat_message("assistant"):
                with st.spinner("Analizando..."):
                    try:
                        answer = ""
                        source_documents = []
                        sources = []
                        
                        # Verificar si el usuario quiere salir del modo aprendizaje
                        if st.session_state.learning_mode and prompt.lower().strip() in ['salir', 'exit', 'terminar', 'fin']:
                            learning_manager = LearningFlowManager(
                                st.session_state.vector_store,
                                st.session_state.session_id
                            )
                            answer = learning_manager.end_learning_session()
                            st.session_state.learning_mode = False
                            st.session_state.learning_topic = None
                            st.session_state.last_learning_content = None
                        
                        # Si estamos en modo aprendizaje, evaluar respuesta
                        elif st.session_state.learning_mode:
                            learning_manager = LearningFlowManager(
                                st.session_state.vector_store,
                                st.session_state.session_id
                            )
                            result = learning_manager.evaluate_answer(
                                user_answer=prompt,
                                topic=st.session_state.learning_topic,
                                previous_content=st.session_state.last_learning_content or ""
                            )
                            answer = result.get("content", "No se pudo evaluar la respuesta.")
                            source_documents = result.get("source_documents", [])
                            st.session_state.last_learning_content = answer
                        
                        else:
                            # Clasificar la query con el router
                            category = route_query(prompt)
                            
                            if category == QueryCategory.CONVERSACION.value:
                                # Respuesta directa sin RAG
                                user_facts = user_memory.get_user_facts_formatted(st.session_state.session_id)
                                answer = get_direct_response(
                                    prompt, 
                                    st.session_state.session_id,
                                    user_facts
                                )
                            
                            elif category == QueryCategory.RESUMEN.value:
                                # Generar resumen
                                result = get_summary_response(
                                    prompt,
                                    st.session_state.vector_store,
                                    st.session_state.session_id
                                )
                                answer = result.get("answer", "No se pudo generar el resumen.")
                                source_documents = result.get("source_documents", [])
                            
                            elif category == QueryCategory.APRENDIZAJE.value:
                                # Iniciar modo aprendizaje
                                learning_manager = LearningFlowManager(
                                    st.session_state.vector_store,
                                    st.session_state.session_id
                                )
                                result = learning_manager.start_learning_session(prompt)
                                answer = result.get("content", "No se pudo iniciar la sesión de aprendizaje.")
                                source_documents = result.get("source_documents", [])
                                
                                if result.get("is_learning_mode"):
                                    st.session_state.learning_mode = True
                                    st.session_state.learning_topic = result.get("topic", prompt)
                                    st.session_state.last_learning_content = answer
                            
                            else:
                                # PREGUNTA_DOCUMENTO u OTRO: usar RAG normal
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
                                # Separar fuentes por tipo
                                video_sources = []
                                doc_sources = []
                                
                                for doc in source_documents:
                                    source = doc.metadata.get("source", "Desconocido")
                                    doc_type = doc.metadata.get("type", "document")
                                    
                                    if doc_type == "video":
                                        video_id = doc.metadata.get("video_id")
                                        timestamp = doc.metadata.get("timestamp", 0)
                                        if video_id and (video_id, timestamp) not in [(v[0], v[1]) for v in video_sources]:
                                            video_sources.append((video_id, timestamp, source))
                                    else:
                                        if source not in doc_sources:
                                            doc_sources.append(source)
                                
                                # Mostrar documentos normales
                                if doc_sources:
                                    st.write("**📄 Documentos:**")
                                    for source in doc_sources:
                                        st.write(f"• {source}")
                                
                                # Mostrar videos con reproductor embebido
                                if video_sources:
                                    st.write("**🎬 Videos:**")
                                    for video_id, timestamp, source in video_sources:
                                        formatted_time = format_timestamp(timestamp)
                                        st.write(f"• Video en {formatted_time}")
                                        video_url = f"https://www.youtube.com/watch?v={video_id}&t={int(timestamp)}s"
                                        st.video(video_url, start_time=int(timestamp))
                        
                        # Agregar respuesta al historial y persistir
                        msg_data = {"role": "assistant", "content": answer}
                        if sources:
                            msg_data["sources"] = sources
                        st.session_state.messages.append(msg_data)
                        chat_manager.save_message(
                            st.session_state.session_id, 
                            "assistant", 
                            answer, 
                            sources if sources else None
                        )
                        
                        # Extraer hechos del usuario de forma asíncrona
                        user_memory.extract_and_save_async(
                            st.session_state.session_id,
                            prompt,
                            answer
                        )
                    
                    except Exception as e:
                        error_msg = f"Error al generar respuesta: {str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": error_msg
                        })
                        chat_manager.save_message(
                            st.session_state.session_id, 
                            "assistant", 
                            error_msg
                        )
    else:
        st.error("Error al inicializar la cadena de conversación. Verifica la configuración.")

# Footer
st.markdown("---")
st.caption("💡 Tip: Puedes pedirle al chatbot que genere preguntas tipo test sobre los documentos subidos.")
