import { BACKEND_URL } from "@/lib/config";
import {
  fetchJson,
  normalizeSessionId,
  parseErrorResponse,
  sessionHeaders,
} from "@/lib/http";

export { BACKEND_URL };

export interface ChatResponse {
  answer: string;
  sources: string[];
  learning_mode: boolean;
  learning_topic: string | null;
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

export interface ClearSessionResponse {
  message: string;
}

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

export interface DashboardCompetencyItem {
  name: string;
  score: number;
}

export interface DashboardDocumentCompetencies {
  document_id: string;
  display_name?: string | null;
  competencies: DashboardCompetencyItem[];
}

export interface DashboardCompetencyResponse {
  documents: DashboardDocumentCompetencies[];
}

export interface GeneratedLearningUnit {
  name: string;
  definition: string;
  weight: number;
}

export interface GeneratedTheme {
  name: string;
  learning_units: GeneratedLearningUnit[];
}

export interface GeneratedItinerary {
  title: string;
  total_weeks: number;
  hours_per_week: number;
  themes: GeneratedTheme[];
}

export interface LearningUnitCreate {
  name: string;
  definition: string;
  weight: number;
  order_index?: number;
  learning_outcome_id?: number | null;
}

export interface TrainerLearningOutcomeOption {
  id: number;
  description: string;
  competency_name: string;
  subcompetency_name: string;
  document_id: string;
}

export interface ThemeCreate {
  name: string;
  order_index?: number;
  learning_units: LearningUnitCreate[];
}

export interface CourseItineraryCreate {
  title: string;
  total_weeks: number;
  hours_per_week: number;
  themes: ThemeCreate[];
}

export interface SaveItineraryResponse {
  itinerary_id: number;
  theme_count: number;
  unit_count: number;
  message: string;
}

export interface QuadrantUnit {
  unit_id: number;
  name: string;
  definition: string;
  weight: number;
  score: number;
  percent_complete: number;
  color_code: string;
}

export interface QuadrantTheme {
  theme_id: number;
  name: string;
  units: QuadrantUnit[];
}

export interface QuadrantResponse {
  itinerary_id: number;
  title: string;
  total_weeks: number;
  hours_per_week: number;
  themes: QuadrantTheme[];
  overall_score: number;
}

export interface StudentActivityLogRead {
  id: number;
  session_id: string;
  learning_unit_id: number;
  activity_type: "video" | "chat_question" | "quiz";
  score_earned: number | null;
  detail: string | null;
  timestamp: string;
}

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
  /** Celda del cuadrante asociada (cuestionario / evaluación de unidad). */
  learning_unit_id?: number;
}

export async function chat(
  message: string,
  sessionId: string,
  options: ChatOptions = {},
  accessToken?: string | null,
): Promise<ChatResponse> {
  return fetchJson<ChatResponse>(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: message.trim(),
      session_id: normalizeSessionId(sessionId),
      temperature: options.temperature ?? 0.7,
      max_tokens: options.max_tokens ?? 65535,
      learning_mode: options.learning_mode ?? false,
      learning_topic: options.learning_topic ?? null,
      last_learning_content: options.last_learning_content ?? null,
      learning_unit_id: options.learning_unit_id ?? null,
    }),
    sessionId,
    accessToken,
  });
}

export async function getHistory(
  sessionId: string,
  accessToken?: string | null,
): Promise<HistoryResponse> {
  return fetchJson<HistoryResponse>(`${BACKEND_URL}/history`, {
    method: "GET",
    sessionId,
    accessToken,
  });
}

export async function clearSession(
  sessionId: string,
  accessToken?: string | null,
): Promise<ClearSessionResponse> {
  return fetchJson<ClearSessionResponse>(`${BACKEND_URL}/session/clear`, {
    method: "POST",
    sessionId,
    accessToken,
  });
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
    credentials: "include",
    signal: options?.signal,
  });
  if (!res.ok) {
    const message = await parseErrorResponse(res);
    throw new Error(message);
  }
  return res.blob();
}

export async function uploadPdf(
  file: File,
  sessionId: string,
  accessToken?: string | null,
): Promise<TaskEnqueuedResponse> {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    throw new Error("Solo se aceptan archivos PDF");
  }
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BACKEND_URL}/upload`, {
    method: "POST",
    headers: sessionHeaders(sessionId, accessToken),
    body: form,
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }
  return res.json() as Promise<TaskEnqueuedResponse>;
}

export async function loadCloudPdfs(
  sessionId: string,
  accessToken?: string | null,
): Promise<TaskEnqueuedResponse> {
  return fetchJson<TaskEnqueuedResponse>(`${BACKEND_URL}/upload/load_cloud`, {
    method: "POST",
    sessionId,
    accessToken,
  });
}

export async function processVideo(
  url: string,
  sessionId: string,
  accessToken?: string | null,
): Promise<TaskEnqueuedResponse> {
  return fetchJson<TaskEnqueuedResponse>(`${BACKEND_URL}/process_video`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: url.trim(), session_id: normalizeSessionId(sessionId) }),
    sessionId,
    accessToken,
  });
}

export async function getTaskStatus(
  taskId: string,
  accessToken?: string | null,
): Promise<TaskStatusResponse> {
  return fetchJson<TaskStatusResponse>(
    `${BACKEND_URL}/status/${encodeURIComponent(taskId)}`,
    { method: "GET", accessToken },
  );
}

export async function getDashboardCompetencies(
  sessionId: string,
  projectDocumentKeys?: readonly string[],
  accessToken?: string | null,
): Promise<DashboardCompetencyResponse> {
  const headers: Record<string, string> = {};
  if (projectDocumentKeys?.length) {
    headers["X-Project-Document-Keys"] = encodeURIComponent(
      JSON.stringify([...projectDocumentKeys]),
    );
  }
  return fetchJson<DashboardCompetencyResponse>(`${BACKEND_URL}/dashboard/competencies`, {
    method: "GET",
    sessionId,
    headers,
    accessToken,
  });
}

// Formador y alumno
export async function getTrainerLearningOutcomes(
  sessionId: string,
  projectDocumentKeys?: readonly string[],
  accessToken?: string | null,
): Promise<TrainerLearningOutcomeOption[]> {
  const headers: Record<string, string> = {};
  if (projectDocumentKeys?.length) {
    headers["X-Project-Document-Keys"] = encodeURIComponent(
      JSON.stringify([...projectDocumentKeys]),
    );
  }
  return fetchJson<TrainerLearningOutcomeOption[]>(
    `${BACKEND_URL}/trainer/learning-outcomes`,
    { method: "GET", sessionId, headers, accessToken },
  );
}

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

export async function getProgressQuadrant(
  studentUsername: string,
  sessionId: string,
  accessToken?: string | null,
): Promise<QuadrantResponse> {
  return fetchJson<QuadrantResponse>(
    `${BACKEND_URL}/trainer/progress/quadrant/${encodeURIComponent(studentUsername)}`,
    { method: "GET", sessionId, accessToken },
  );
}

export interface UserOut {
  id: number;
  username: string;
  email?: string | null;
  role: "formador" | "alumno";
  created_at: string;
}

export interface StudentListResponse {
  students: UserOut[];
}

export interface SharedProjectDocument {
  name: string;
  doc_key: string;
  source: string;
}

export interface SharedProjectRead {
  id: number;
  name: string;
  session_id: string;
  trainer_username: string;
  documents: SharedProjectDocument[];
}

export interface SharedProjectsResponse {
  projects: SharedProjectRead[];
}

/** GET /student/projects/shared — Cursos del formador asignados al alumno. */
export async function getSharedProjects(
  sessionId: string,
  accessToken?: string | null,
): Promise<SharedProjectsResponse> {
  return fetchJson<SharedProjectsResponse>(`${BACKEND_URL}/student/projects/shared`, {
    method: "GET",
    sessionId,
    accessToken,
  });
}

/**
 * GET /student/progress/quadrant/me — Cuadrante del alumno en el curso activo (header X-Session-Id).
 */
export async function getMyProgressQuadrant(
  sessionId: string,
  accessToken?: string | null,
): Promise<QuadrantResponse> {
  return fetchJson<QuadrantResponse>(`${BACKEND_URL}/student/progress/quadrant/me`, {
    method: "GET",
    sessionId,
    accessToken,
  });
}

/** GET /trainer/students/available */
export async function getAvailableStudents(
  sessionId: string,
  accessToken?: string | null,
): Promise<StudentListResponse> {
  return fetchJson<StudentListResponse>(`${BACKEND_URL}/trainer/students/available`, {
    method: "GET",
    sessionId,
    accessToken,
  });
}

/** GET /trainer/students/mine */
export async function getMyStudents(
  sessionId: string,
  accessToken?: string | null,
): Promise<StudentListResponse> {
  return fetchJson<StudentListResponse>(`${BACKEND_URL}/trainer/students/mine`, {
    method: "GET",
    sessionId,
    accessToken,
  });
}

/** POST /trainer/students/assign */
export async function assignStudent(
  body: { student_id?: number; student_username?: string },
  sessionId: string,
  accessToken?: string | null,
): Promise<UserOut> {
  return fetchJson<UserOut>(`${BACKEND_URL}/trainer/students/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    sessionId,
    accessToken,
  });
}

/** DELETE /trainer/students/remove/{username} */
export async function removeStudent(
  studentUsername: string,
  sessionId: string,
  accessToken?: string | null,
): Promise<void> {
  await fetchJson<void>(
    `${BACKEND_URL}/trainer/students/remove/${encodeURIComponent(studentUsername)}`,
    { method: "DELETE", sessionId, accessToken },
  );
}

export async function getUnitDetails(
  studentUsername: string,
  unitId: number,
  sessionId: string,
  accessToken?: string | null,
): Promise<UnitDetailsResponse> {
  return fetchJson<UnitDetailsResponse>(
    `${BACKEND_URL}/trainer/progress/unit-details/${encodeURIComponent(studentUsername)}/${unitId}`,
    { method: "GET", sessionId, accessToken },
  );
}
