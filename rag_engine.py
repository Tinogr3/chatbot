"""
Módulo de motor RAG (Retrieval Augmented Generation).
Contiene la lógica de LangChain, embeddings, procesamiento de PDFs y creación de chains.
"""
import os
import re
import time
from pathlib import Path
from typing import List, Optional

import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate

from config import get_credentials_and_project
from user_memory import UserMemoryManager


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
                "\\n\\n",  # Saltos de párrafo (prioridad más alta)
                "\\n",    # Saltos de línea
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
    session_id: str = None
):
    """Inicializa la cadena de conversación con memoria.
    
    Args:
        vector_store: El vector store a usar para retrieval
        temperature: Nivel de creatividad del modelo
        max_tokens: Límite de tokens en la respuesta
        session_id: ID de sesión para cargar hechos del usuario
    
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
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-2.0-flash-exp",
                temperature=temperature,
                max_output_tokens=max_tokens,
                api_key=api_key
            )
        else:
            # Usar Vertex AI con credenciales de servicio
            llm = ChatGoogleGenerativeAI(
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-2.0-flash-exp",
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
        system_template = f"""Eres un tutor universitario experto y preciso. Sigue estas instrucciones estrictamente:{user_facts_section}

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
{{context}}

PREGUNTA DEL USUARIO:
{{question}}

RESPUESTA (piensa paso a paso, cita las fuentes, sé preciso):"""
        
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
