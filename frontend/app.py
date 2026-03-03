"""
Frontend Streamlit - Chatbot RAG Educativo (cliente del backend).
Solo UI y st.session_state; toda la lógica pesada está en el backend vía API.
"""
import os
import logging

import streamlit as st

from api_client import (
    chat as api_chat,
    upload_pdf,
    load_cloud_pdfs,
    process_video as api_process_video,
    get_history as api_get_history,
    get_user_facts as api_get_user_facts,
    delete_user_facts as api_delete_user_facts,
    clear_session as api_clear_session,
)
from utils import format_timestamp, extract_video_id, is_youtube_url

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Chatbot RAG Educativo", page_icon="📚", layout="wide")

# --- Sesión ---
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def show_welcome_screen():
    st.title("📚 Bienvenido al Chatbot RAG Educativo")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        ### 👋 ¡Hola!
        Para comenzar, ingresa tu **nombre de usuario** o **ID de sesión**.
        - 💾 Guardar tu historial de conversaciones
        - 🧠 Recordar información sobre ti
        - 📊 Continuar donde lo dejaste
        """)
        with st.form("login_form"):
            username = st.text_input(
                "Nombre de Usuario / ID de Sesión",
                placeholder="Ej: juan_perez, mi_sesion_123",
                help="Usa el mismo nombre para recuperar tu historial en futuras sesiones",
            )
            submit = st.form_submit_button("🚀 Comenzar", use_container_width=True)
            if submit:
                if username and username.strip():
                    clean_username = username.strip().lower().replace(" ", "_")
                    st.session_state.session_id = clean_username
                    st.session_state.authenticated = True
                    try:
                        messages = api_get_history(clean_username)
                        st.session_state.messages = messages
                        user_facts = api_get_user_facts(clean_username)
                        if user_facts:
                            st.success(f"¡Bienvenido de nuevo! Se cargaron {len(user_facts)} datos sobre ti.")
                        else:
                            st.success(f"¡Bienvenido, {username}! Se creó una nueva sesión.")
                    except Exception as e:
                        st.session_state.messages = []
                        st.success(f"¡Bienvenido, {username}!")
                        logger.warning("Error loading history/user_facts: %s", e)
                    st.rerun()
                else:
                    st.error("Por favor, ingresa un nombre de usuario válido.")
        st.info("💡 **Tip:** Usa siempre el mismo nombre para mantener tu historial y preferencias.")


if not st.session_state.authenticated:
    show_welcome_screen()
    st.stop()

# --- Estado de sesión (solo frontend) ---
session_id = st.session_state.session_id
if "messages" not in st.session_state:
    try:
        st.session_state.messages = api_get_history(session_id)
    except Exception:
        st.session_state.messages = []

if "modo_operacion" not in st.session_state:
    st.session_state.modo_operacion = "Nube Automático"
if "max_tokens" not in st.session_state:
    st.session_state.max_tokens = 65535
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.7
if "archivos_manuales" not in st.session_state:
    st.session_state.archivos_manuales = []
if "archivos_nube" not in st.session_state:
    st.session_state.archivos_nube = []
if "videos_procesados" not in st.session_state:
    st.session_state.videos_procesados = []
if "learning_mode" not in st.session_state:
    st.session_state.learning_mode = False
if "learning_topic" not in st.session_state:
    st.session_state.learning_topic = None
if "last_learning_content" not in st.session_state:
    st.session_state.last_learning_content = None

# --- Sidebar ---
with st.sidebar:
    st.markdown(f"👤 **Usuario:** `{session_id}`")
    if st.button("🚪 Cerrar Sesión", help="Cierra sesión para cambiar de usuario"):
        st.session_state.session_id = None
        st.session_state.authenticated = False
        st.session_state.messages = []
        st.session_state.archivos_manuales = []
        st.session_state.archivos_nube = []
        st.session_state.videos_procesados = []
        st.rerun()

    st.divider()
    with st.expander("🧠 Lo que sé de ti", expanded=False):
        try:
            user_facts = api_get_user_facts(session_id)
        except Exception:
            user_facts = []
        if user_facts:
            facts_by_type = {}
            type_icons = {
                "nombre": "👤", "trabajo": "💼", "educacion": "🎓",
                "stack_tecnologico": "💻", "preferencias": "⭐",
                "ubicacion": "📍", "otro": "📝",
            }
            type_labels = {
                "nombre": "Nombre", "trabajo": "Trabajo", "educacion": "Educación",
                "stack_tecnologico": "Stack", "preferencias": "Intereses",
                "ubicacion": "Ubicación", "otro": "Otros",
            }
            for fact in user_facts:
                t = fact.get("tipo", "otro")
                if t not in facts_by_type:
                    facts_by_type[t] = []
                facts_by_type[t].append(fact.get("valor", ""))
            for tipo, valores in facts_by_type.items():
                st.markdown(f"**{type_icons.get(tipo, '📝')} {type_labels.get(tipo, tipo)}:**")
                tags = " ".join(
                    f'<span style="background-color: #262730; padding: 2px 8px; border-radius: 12px; margin: 2px; display: inline-block; font-size: 0.85em;">{v}</span>'
                    for v in valores
                )
                st.markdown(tags, unsafe_allow_html=True)
            if st.button("🗑️ Olvídame", help="Borra toda la información que sé sobre ti", key="forget_me"):
                try:
                    n = api_delete_user_facts(session_id)
                    st.success(f"✅ Se eliminaron {n} datos sobre ti.")
                except Exception as e:
                    st.error(f"Error: {e}")
                st.rerun()
        else:
            st.caption("Aún no sé nada sobre ti. A medida que conversemos, iré aprendiendo.")

    st.divider()
    st.header("⚙️ Configuración")
    st.subheader("🔀 Modo de Operación")
    modo_anterior = st.session_state.modo_operacion
    modo_operacion = st.radio(
        "Modo de Operación",
        ["Nube Automático", "Manual (Upload)", "Híbrido (Todo)"],
        index=["Nube Automático", "Manual (Upload)", "Híbrido (Todo)"].index(st.session_state.modo_operacion),
        help="Elige cómo quieres gestionar los documentos del chatbot",
    )
    if modo_operacion != modo_anterior:
        st.session_state.modo_operacion = modo_operacion
        try:
            api_clear_session(session_id)
        except Exception:
            pass
        st.session_state.messages = []
        st.session_state.archivos_manuales = []
        st.session_state.archivos_nube = []
        st.session_state.videos_procesados = []
        st.rerun()

    if modo_operacion == "Nube Automático":
        st.subheader("☁️ Modo Nube Automático")
        st.info("Este modo procesa automáticamente todos los PDFs del bucket.")
        if st.button("🔄 Cargar Todos los PDFs del Bucket"):
            with st.spinner("Descargando y procesando todos los PDFs..."):
                try:
                    resp = load_cloud_pdfs(session_id)
                    if resp.get("success"):
                        st.session_state.archivos_nube = resp.get("filenames", [])
                        st.success(f"✅ {resp.get('message', '')}")
                        st.info(f"Se generaron {resp.get('document_count', 0)} chunks con embeddings.")
                    else:
                        st.warning(resp.get("message", "Error al cargar desde la nube."))
                except Exception as e:
                    st.error(f"Error: {e}")
                st.rerun()
        if st.session_state.archivos_nube:
            st.subheader("📚 Archivos de la Nube")
            for f in st.session_state.archivos_nube:
                st.write(f"☁️ {f}")

    elif modo_operacion == "Manual (Upload)":
        st.subheader("📤 Modo Manual (Upload)")
        st.info("Solo se consideran los archivos que subas manualmente en esta sesión.")
        uploaded_file = st.file_uploader("Selecciona un archivo PDF", type=["pdf"], help="Sube un PDF para procesarlo.")
        if uploaded_file is not None and st.button("Procesar y Subir PDF"):
            with st.spinner("Procesando documento..."):
                try:
                    content = uploaded_file.read()
                    resp = upload_pdf(content, uploaded_file.name, session_id)
                    if resp.get("success"):
                        fn = resp.get("filename", uploaded_file.name)
                        if fn not in st.session_state.archivos_manuales:
                            st.session_state.archivos_manuales.append(fn)
                        st.success(resp.get("message", "✅ Archivo cargado."))
                        st.info(f"Se generaron {resp.get('document_count', 0)} chunks.")
                    else:
                        st.error(resp.get("message", "Error al procesar."))
                except Exception as e:
                    st.error(f"Error: {e}")
                st.rerun()
        if st.session_state.archivos_manuales:
            st.subheader("📚 Archivos Manuales")
            for f in st.session_state.archivos_manuales:
                st.write(f"📄 {f}")

    else:
        st.subheader("🔄 Modo Híbrido (Todo)")
        st.info("Combina documentos de la nube con los que subas manualmente.")
        st.markdown("#### ☁️ Documentos de la Nube")
        if st.button("🔄 Cargar Todos los PDFs del Bucket"):
            with st.spinner("Descargando y procesando..."):
                try:
                    resp = load_cloud_pdfs(session_id)
                    if resp.get("success"):
                        st.session_state.archivos_nube = resp.get("filenames", [])
                        st.success(resp.get("message", ""))
                    else:
                        st.warning(resp.get("message", ""))
                except Exception as e:
                    st.error(str(e))
                st.rerun()
        if st.session_state.archivos_nube:
            for f in st.session_state.archivos_nube:
                st.write(f"☁️ {f}")
        st.divider()
        st.markdown("#### 📤 Subir Archivo Manual")
        uploaded_file = st.file_uploader("Selecciona un archivo PDF", type=["pdf"], key="hybrid_upload")
        if uploaded_file is not None and st.button("Procesar y Subir PDF"):
            with st.spinner("Procesando..."):
                try:
                    resp = upload_pdf(uploaded_file.read(), uploaded_file.name, session_id)
                    if resp.get("success"):
                        fn = resp.get("filename", uploaded_file.name)
                        if fn not in st.session_state.archivos_manuales:
                            st.session_state.archivos_manuales.append(fn)
                        st.success(resp.get("message", ""))
                    else:
                        st.error(resp.get("message", ""))
                except Exception as e:
                    st.error(str(e))
                st.rerun()
        if st.session_state.archivos_manuales:
            for f in st.session_state.archivos_manuales:
                st.write(f"📄 {f}")

    st.divider()
    st.subheader("🎬 Videos de YouTube")
    st.info("Añade videos de YouTube para extraer conocimiento de sus transcripciones.")
    youtube_url = st.text_input("URL del video de YouTube", placeholder="https://www.youtube.com/watch?v=...")
    if youtube_url and st.button("🎥 Procesar Video"):
        if is_youtube_url(youtube_url):
            with st.spinner("Extrayendo transcripción del video..."):
                try:
                    resp = api_process_video(youtube_url, session_id)
                    if resp.get("success"):
                        if youtube_url not in st.session_state.videos_procesados:
                            st.session_state.videos_procesados.append(youtube_url)
                        st.success("✅ Video procesado correctamente.")
                        st.info(f"Se generaron {resp.get('document_count', 0)} chunks con timestamps.")
                    else:
                        st.warning(resp.get("message", ""))
                except Exception as e:
                    st.error(str(e))
            st.rerun()
        else:
            st.error("Por favor, introduce una URL válida de YouTube.")
    if st.session_state.videos_procesados:
        for url in st.session_state.videos_procesados:
            st.write(f"🎬 `{extract_video_id(url) or url}`")

    st.divider()
    st.subheader("🧹 Gestión de Sesión")
    if st.button("🗑️ Limpiar Memoria", help="Borra el historial del chat y el vector store para empezar de cero"):
        try:
            api_clear_session(session_id)
            st.session_state.messages = []
            st.session_state.archivos_manuales = []
            st.session_state.archivos_nube = []
            st.session_state.videos_procesados = []
            st.session_state.learning_mode = False
            st.session_state.learning_topic = None
            st.session_state.last_learning_content = None
            st.success("✅ Memoria limpiada exitosamente.")
        except Exception as e:
            st.error(str(e))
        st.rerun()

    st.divider()
    st.subheader("🎛️ Parámetros del Modelo")
    st.session_state["temperature"] = st.slider("Nivel de Creatividad (Temperature)", 0.0, 2.0, st.session_state.get("temperature", 0.7), 0.1)
    st.session_state["max_tokens"] = st.slider("Límite de Tokens", 256, 65535, st.session_state.get("max_tokens", 65535), 256)

# --- Área principal del chat ---
st.title("📚 Chatbot RAG Educativo")
st.markdown("---")

# Mostrar historial
for message in st.session_state.messages:
    with st.chat_message(message.get("role", "user")):
        st.markdown(message.get("content", ""))
        if message.get("sources"):
            with st.expander("📄 Fuentes utilizadas"):
                for s in message["sources"]:
                    st.write(f"• {s}")

if st.session_state.learning_mode:
    st.info("🎓 **Modo Aprendizaje activo** - Responde las preguntas para continuar. Escribe 'salir' para terminar.")

if prompt := st.chat_input("Escribe tu pregunta aquí..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analizando..."):
            try:
                resp = api_chat(
                    message=prompt,
                    session_id=session_id,
                    temperature=st.session_state.get("temperature", 0.7),
                    max_tokens=st.session_state.get("max_tokens", 65535),
                    learning_mode=st.session_state.learning_mode,
                    learning_topic=st.session_state.learning_topic,
                    last_learning_content=st.session_state.last_learning_content,
                )
                answer = resp.get("answer", "")
                sources = resp.get("sources", [])
                st.session_state.learning_mode = resp.get("learning_mode", False)
                st.session_state.learning_topic = resp.get("learning_topic")
                st.session_state.last_learning_content = answer
                st.markdown(answer)
                if sources:
                    with st.expander("📄 Fuentes utilizadas"):
                        for s in sources:
                            st.write(f"• {s}")
                msg_data = {"role": "assistant", "content": answer}
                if sources:
                    msg_data["sources"] = sources
                st.session_state.messages.append(msg_data)
                st.toast("🧠 Analizando memoria...", icon="💾")
            except Exception as e:
                logger.exception("Chat error: %s", e)
                err = f"Error al generar respuesta: {str(e)}"
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})
    st.rerun()

st.markdown("---")
st.caption("💡 Tip: Puedes pedirle al chatbot que genere preguntas tipo test sobre los documentos subidos.")
