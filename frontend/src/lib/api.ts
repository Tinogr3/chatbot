/**
 * Cliente API para el backend FastAPI del Chatbot RAG Educativo.
 * Usa fetch nativo. Todas las funciones incluyen X-Session-Id cuando aplica.
 */

/** URL base del backend FastAPI. Override con NEXT_PUBLIC_BACKEND_URL. */
export const BACKEND_URL =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_BACKEND_URL) ||
  "http://localhost:8000";

// ---------------------------------------------------------------------------
// Tipos de respuesta (alineados con backend/schemas.py)
// ---------------------------------------------------------------------------

export interface ChatResponse {
  answer: string;
  sources: string[];
  learning_mode: boolean;
  learning_topic: string | null;
  /**
   * El backend lo activa cuando, dentro de un flujo de modo aprendizaje, ha
   * persistido una nueva `LearningEvidence` y recalculado el progreso de la
   * subcompetencia. El frontend usa este flag como señal para refrescar el
   * dashboard de competencias. Se marca opcional para permanecer compatible
   * con respuestas antiguas que no incluían el campo.
   */
  progress_updated?: boolean;
}

export interface ChatMessageSchema {
  role: string;
  content: string;
  sources?: string[] | null;
}

export interface HistoryResponse {
  messages: ChatMessageSchema[];
}

export interface UserFactItem {
  tipo: string;
  valor: string;
  confianza: number;
}

export interface UserFactsResponse {
  facts: UserFactItem[];
}

export interface ClearSessionResponse {
  message: string;
}

/** Discovery Hub — resúmenes y exámenes persistidos por sesión. */
export interface DiscoveryItem {
  id: number;
  user_prompt: string;
  content: string;
  created_at: string;
}

export interface DiscoveryStats {
  summaries: number;
  exams: number;
}

export interface DeletedCountResponse {
  deleted: number;
}

export interface TaskEnqueuedResponse {
  task_id: string;
  message: string;
}

export interface TaskStatusResponse {
  task_id: string;
  status: "PENDING" | "PROGRESS" | "SUCCESS" | "FAILURE";
  progress: number;
  message: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface LoadCloudResponse {
  success: boolean;
  filenames: string[];
  document_count: number;
  message: string;
}

// ---------------------------------------------------------------------------
// Tipos de Dashboard / Evaluación
// (Espejo TypeScript de los esquemas Pydantic en backend/schemas.py)
// ---------------------------------------------------------------------------

/**
 * Espejo de `DashboardCompetencyItem`.
 * Puntuación 0.0–1.0: promedio de subcompetencias en modo aprendizaje.
 * El UI la muestra como escala 0–5.
 */
export interface DashboardCompetencyItem {
  name: string;
  score: number;
}

/** Espejo de `DashboardDocumentCompetencies`. */
export interface DashboardDocumentCompetencies {
  document_id: string;
  /** Nombre legible (título del vídeo, nombre del PDF). Presente si el backend lo conoce. */
  display_name?: string | null;
  competencies: DashboardCompetencyItem[];
}

/**
 * Espejo de `DashboardCompetencyResponse`.
 * Respuesta de `GET /dashboard/competencies`: un bloque por documento cargado.
 */
export interface DashboardCompetencyResponse {
  documents: DashboardDocumentCompetencies[];
}

/**
 * Espejo de `EvaluateLearningRequest`.
 * Body que se envía a `POST /evaluate` para que el backend evalúe la
 * respuesta del estudiante con el LLM, registre la evidencia y actualice
 * la puntuación agregada de la subcompetencia correspondiente.
 */
export interface EvaluateLearningRequest {
  session_id: string;
  learning_outcome_id: number;
  answer: string;
}

/**
 * Espejo de `EvaluateLearningResponse`.
 * Devuelve la puntuación asignada a la respuesta concreta, el feedback
 * generado por el evaluador y la puntuación recalculada de la subcompetencia
 * tras esta evaluación.
 */
export interface EvaluateLearningResponse {
  score: number;
  feedback: string;
  updated_subcompetency_score: number;
}

// ---------------------------------------------------------------------------
// Tipos del Módulo Formador (espejo de backend/schemas.py)
// ---------------------------------------------------------------------------

/** Espejo de `GeneratedLearningUnit` — pesos en % (0-100). */
export interface GeneratedLearningUnit {
  name: string;
  definition: string;
  weight: number;
}

/** Espejo de `GeneratedTheme`. */
export interface GeneratedTheme {
  name: string;
  learning_units: GeneratedLearningUnit[];
}

/** Espejo de `GeneratedItinerary` — respuesta de POST /trainer/generate-itinerary. */
export interface GeneratedItinerary {
  title: string;
  total_weeks: number;
  hours_per_week: number;
  themes: GeneratedTheme[];
}

/** Unidad a guardar — peso como fracción (0.0-1.0). */
export interface LearningUnitCreate {
  name: string;
  definition: string;
  weight: number;
  order_index?: number;
}

export interface ThemeCreate {
  name: string;
  order_index?: number;
  learning_units: LearningUnitCreate[];
}

/** Espejo de `CourseItineraryCreate` — body de POST /trainer/save-itinerary. */
export interface CourseItineraryCreate {
  title: string;
  total_weeks: number;
  hours_per_week: number;
  themes: ThemeCreate[];
}

/** Espejo de `SaveItineraryResponse`. */
export interface SaveItineraryResponse {
  itinerary_id: number;
  theme_count: number;
  unit_count: number;
  message: string;
}

/** Espejo de `QuadrantUnit` — celda del cuadrante de progreso. */
export interface QuadrantUnit {
  unit_id: number;
  name: string;
  definition: string;
  weight: number;
  score: number;
  percent_complete: number;
  color_code: string;
}

/** Espejo de `QuadrantTheme`. */
export interface QuadrantTheme {
  theme_id: number;
  name: string;
  units: QuadrantUnit[];
}

/** Espejo de `QuadrantResponse` — GET /trainer/progress/quadrant. */
export interface QuadrantResponse {
  itinerary_id: number;
  title: string;
  total_weeks: number;
  hours_per_week: number;
  themes: QuadrantTheme[];
  overall_score: number;
}

/** Espejo de `StudentActivityLogRead`. */
export interface StudentActivityLogRead {
  id: number;
  session_id: string;
  learning_unit_id: number;
  activity_type: "video" | "chat_question" | "quiz";
  score_earned: number | null;
  detail: string | null;
  timestamp: string;
}

/** Espejo de `UnitDetailsResponse` — GET /trainer/progress/unit-details. */
export interface UnitDetailsResponse {
  unit_id: number;
  unit_name: string;
  total_score: number;
  color_code: string;
  quiz_stats: { count: number; average_score: number | null };
  video_count: number;
  chat_question_count: number;
  quiz_points: number;
  action_points: number;
  activities: StudentActivityLogRead[];
}

// ---------------------------------------------------------------------------
// Opciones de chat (request body POST /chat)
// ---------------------------------------------------------------------------

export interface ChatOptions {
  temperature?: number;
  max_tokens?: number;
  learning_mode?: boolean;
  learning_topic?: string | null;
  last_learning_content?: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sessionHeaders(sessionId: string, accessToken?: string | null): HeadersInit {
  const h: Record<string, string> = {
    "X-Session-Id": sessionId.trim().toLowerCase().replace(/\s+/g, "_"),
  };
  if (accessToken) h["Authorization"] = `Bearer ${accessToken}`;
  return h;
}

async function parseErrorResponse(res: Response): Promise<string> {
  const text = await res.text();
  let detail: string;
  try {
    const json = JSON.parse(text) as { detail?: string | Array<{ msg?: string }> };
    if (typeof json.detail === "string") {
      detail = json.detail;
    } else if (Array.isArray(json.detail)) {
      detail = json.detail.map((d) => (d && d.msg) || String(d)).join("; ");
    } else {
      detail = text || res.statusText || `Error ${res.status}`;
    }
  } catch {
    detail = text || res.statusText || `Error ${res.status}`;
  }
  return detail;
}

async function fetchJson<T>(
  url: string,
  options: RequestInit & { sessionId?: string; accessToken?: string | null } = {}
): Promise<T> {
  const { sessionId, accessToken, ...init } = options;
  const headers = new Headers(init.headers as Headers);
  if (sessionId !== undefined) {
    headers.set("X-Session-Id", sessionId.trim().toLowerCase().replace(/\s+/g, "_"));
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const message = await parseErrorResponse(res);
    throw new Error(message);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

/**
 * POST /chat — Envía un mensaje y devuelve la respuesta del asistente.
 */
export async function chat(
  message: string,
  sessionId: string,
  options: ChatOptions = {},
  accessToken?: string | null,
): Promise<ChatResponse> {
  const body = {
    message: message.trim(),
    session_id: sessionId.trim().toLowerCase().replace(/\s+/g, "_"),
    temperature: options.temperature ?? 0.7,
    max_tokens: options.max_tokens ?? 65535,
    learning_mode: options.learning_mode ?? false,
    learning_topic: options.learning_topic ?? null,
    last_learning_content: options.last_learning_content ?? null,
  };
  try {
    return await fetchJson<ChatResponse>(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      sessionId,
      accessToken,
    });
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

/**
 * GET /history — Obtiene el historial de mensajes de la sesión.
 */
export async function getHistory(sessionId: string, accessToken?: string | null): Promise<HistoryResponse> {
  try {
    return await fetchJson<HistoryResponse>(`${BACKEND_URL}/history`, {
      method: "GET",
      sessionId,
      accessToken,
    });
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

/**
 * DELETE /history — Borra el historial de chat de la sesión.
 */
export async function deleteHistory(sessionId: string, accessToken?: string | null): Promise<DeletedCountResponse> {
  try {
    return await fetchJson<DeletedCountResponse>(`${BACKEND_URL}/history`, {
      method: "DELETE",
      sessionId,
      accessToken,
    });
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

/**
 * GET /user_facts — Obtiene los hechos almacenados sobre el usuario.
 */
export async function getUserFacts(sessionId: string, accessToken?: string | null): Promise<UserFactsResponse> {
  try {
    return await fetchJson<UserFactsResponse>(`${BACKEND_URL}/user_facts`, {
      method: "GET",
      sessionId,
      accessToken,
    });
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

/**
 * DELETE /user_facts — Borra todos los hechos del usuario.
 */
export async function deleteUserFacts(sessionId: string, accessToken?: string | null): Promise<DeletedCountResponse> {
  try {
    return await fetchJson<DeletedCountResponse>(`${BACKEND_URL}/user_facts`, {
      method: "DELETE",
      sessionId,
      accessToken,
    });
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

/**
 * POST /session/clear — Limpia historial, documentos y vector store de la sesión.
 */
export async function clearSession(sessionId: string, accessToken?: string | null): Promise<ClearSessionResponse> {
  try {
    return await fetchJson<ClearSessionResponse>(`${BACKEND_URL}/session/clear`, {
      method: "POST",
      sessionId,
      accessToken,
    });
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

/**
 * GET /discovery/stats — Conteos de resúmenes y exámenes guardados para la sesión.
 */
export async function getDiscoveryStats(sessionId: string, accessToken?: string | null): Promise<DiscoveryStats> {
  return fetchJson<DiscoveryStats>(`${BACKEND_URL}/discovery/stats`, {
    method: "GET",
    sessionId,
    accessToken,
  });
}

/**
 * GET /discovery/summaries — Lista de resúmenes generados desde el chat.
 */
export async function getDiscoverySummaries(sessionId: string, accessToken?: string | null): Promise<DiscoveryItem[]> {
  return fetchJson<DiscoveryItem[]>(`${BACKEND_URL}/discovery/summaries`, {
    method: "GET",
    sessionId,
    accessToken,
  });
}

/**
 * GET /discovery/exams — Lista de exámenes generados desde el chat.
 */
export async function getDiscoveryExams(sessionId: string, accessToken?: string | null): Promise<DiscoveryItem[]> {
  return fetchJson<DiscoveryItem[]>(`${BACKEND_URL}/discovery/exams`, {
    method: "GET",
    sessionId,
    accessToken,
  });
}

/**
 * POST /discovery/podcast-audio — Genera MP3 a partir de resúmenes guardados.
 * Si ``summaryIds`` tiene al menos un id, solo esos (en ese orden); si se omite,
 * el backend incluye todos los resúmenes de la sesión (cuerpo vacío / sin ids).
 */
export async function createPodcastAudio(
  sessionId: string,
  summaryIds?: number[],
  options?: { signal?: AbortSignal; accessToken?: string | null }
): Promise<Blob> {
  const headers = new Headers(sessionHeaders(sessionId, options?.accessToken));
  let body: string | undefined;
  if (summaryIds !== undefined) {
    if (summaryIds.length === 0) {
      throw new Error("Selecciona al menos un resumen para el podcast.");
    }
    headers.set("Content-Type", "application/json");
    body = JSON.stringify({ summary_ids: summaryIds });
  }
  const res = await fetch(`${BACKEND_URL}/discovery/podcast-audio`, {
    method: "POST",
    headers,
    body,
    signal: options?.signal,
  });
  if (!res.ok) {
    const message = await parseErrorResponse(res);
    throw new Error(message);
  }
  return res.blob();
}

/**
 * POST /upload — Sube un PDF (encola tarea). Usar getTaskStatus(task_id) para el progreso.
 */
export async function uploadPdf(file: File, sessionId: string, accessToken?: string | null): Promise<TaskEnqueuedResponse> {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    throw new Error("Solo se aceptan archivos PDF");
  }
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await fetch(`${BACKEND_URL}/upload`, {
      method: "POST",
      headers: sessionHeaders(sessionId, accessToken),
      body: form,
    });
    if (!res.ok) {
      const message = await parseErrorResponse(res);
      throw new Error(message);
    }
    return res.json() as Promise<TaskEnqueuedResponse>;
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

/**
 * POST /upload/load_cloud — Carga todos los PDFs del bucket para la sesión.
 */
export async function loadCloudPdfs(sessionId: string, accessToken?: string | null): Promise<TaskEnqueuedResponse> {
  try {
    return await fetchJson<TaskEnqueuedResponse>(`${BACKEND_URL}/upload/load_cloud`, {
      method: "POST",
      sessionId,
      accessToken,
    });
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

/**
 * POST /process_video — Encola el procesamiento de un video de YouTube.
 * Usar getTaskStatus(task_id) para el progreso.
 */
export async function processVideo(
  url: string,
  sessionId: string,
  accessToken?: string | null,
): Promise<TaskEnqueuedResponse> {
  try {
    return await fetchJson<TaskEnqueuedResponse>(`${BACKEND_URL}/process_video`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url.trim(), session_id: sessionId.trim().toLowerCase().replace(/\s+/g, "_") }),
      sessionId,
      accessToken,
    });
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

/**
 * GET /status/{task_id} — Consulta el estado de una tarea (upload o process_video).
 */
export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  try {
    const res = await fetch(`${BACKEND_URL}/status/${encodeURIComponent(taskId)}`);
    if (!res.ok) {
      const message = await parseErrorResponse(res);
      throw new Error(message);
    }
    return res.json() as Promise<TaskStatusResponse>;
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

/**
 * GET /dashboard/competencies — Agrega opcionalmente los nombres de documentos del
 * proyecto (header `X-Project-Document-Keys`) para no depender solo del registro en disco.
 */
export async function getDashboardCompetencies(
  sessionId: string,
  /** Claves de búsqueda de documentos (docKey, no el nombre de display). */
  projectDocumentKeys?: readonly string[],
  accessToken?: string | null,
): Promise<DashboardCompetencyResponse> {
  try {
    const headers: Record<string, string> = {};
    if (projectDocumentKeys?.length) {
      // encodeURIComponent garantiza que el valor sea ASCII puro (los títulos
      // de vídeos de YouTube pueden contener caracteres fuera de ISO-8859-1
      // que el constructor Headers del navegador rechaza con TypeError).
      headers["X-Project-Document-Keys"] = encodeURIComponent(
        JSON.stringify([...projectDocumentKeys]),
      );
    }
    return await fetchJson<DashboardCompetencyResponse>(
      `${BACKEND_URL}/dashboard/competencies`,
      {
        method: "GET",
        sessionId,
        headers,
        accessToken,
      },
    );
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

/**
 * POST /evaluate — Envía la respuesta de un estudiante para que el backend
 * la evalúe con el LLM, registre la evidencia y actualice el progreso de la
 * subcompetencia. Incluye `X-Session-Id` además del `session_id` en el body
 * (el backend lo necesita para indexar la evidencia y el progreso).
 *
 * Errores: 400 (session_id vacío), 404 (`learning_outcome_id` no existe),
 * 502 (LLM no disponible) y 500 (errores de BD/inesperados) se propagan
 * como `Error` con el `detail` del backend.
 */
export async function submitEvaluation(
  data: EvaluateLearningRequest,
  sessionId: string,
  accessToken?: string | null,
): Promise<EvaluateLearningResponse> {
  try {
    return await fetchJson<EvaluateLearningResponse>(`${BACKEND_URL}/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
      sessionId,
      accessToken,
    });
  } catch (e) {
    throw e instanceof Error ? e : new Error(String(e));
  }
}

// ---------------------------------------------------------------------------
// Módulo Formador
// ---------------------------------------------------------------------------

/**
 * POST /trainer/generate-itinerary — Genera el cuadrante con IA (no persiste).
 */
export async function generateItinerary(
  prompt: string,
  sessionId: string,
  accessToken?: string | null,
): Promise<GeneratedItinerary> {
  return fetchJson<GeneratedItinerary>(`${BACKEND_URL}/trainer/generate-itinerary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: prompt.trim() }),
    sessionId,
    accessToken,
  });
}

/**
 * POST /trainer/save-itinerary — Persiste el cuadrante validado por el formador.
 */
export async function saveItinerary(
  itinerary: CourseItineraryCreate,
  sessionId: string,
  accessToken?: string | null,
): Promise<SaveItineraryResponse> {
  return fetchJson<SaveItineraryResponse>(`${BACKEND_URL}/trainer/save-itinerary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(itinerary),
    sessionId,
    accessToken,
  });
}

/**
 * GET /trainer/progress/quadrant/{session_id} — Matriz de progreso del alumno.
 */
export async function getProgressQuadrant(
  studentSessionId: string,
  sessionId: string,
  accessToken?: string | null,
): Promise<QuadrantResponse> {
  return fetchJson<QuadrantResponse>(
    `${BACKEND_URL}/trainer/progress/quadrant/${encodeURIComponent(studentSessionId)}`,
    { method: "GET", sessionId, accessToken },
  );
}

/**
 * GET /trainer/progress/unit-details/{session_id}/{unit_id} — Drill-down de una celda.
 */
export async function getUnitDetails(
  studentSessionId: string,
  unitId: number,
  sessionId: string,
  accessToken?: string | null,
): Promise<UnitDetailsResponse> {
  return fetchJson<UnitDetailsResponse>(
    `${BACKEND_URL}/trainer/progress/unit-details/${encodeURIComponent(studentSessionId)}/${unitId}`,
    { method: "GET", sessionId, accessToken },
  );
}
