"use client";

import { useEffect } from "react";

/**
 * Pub/sub mínimo y desacoplado para señalizar que el progreso de
 * competencias del usuario ha sido actualizado en backend (vía un flujo de
 * chat en modo aprendizaje, una llamada explícita a `POST /evaluate`, etc.).
 *
 * Diseño:
 *  - Un único `CustomEvent` global en `window` (no requiere Provider extra
 *    en el árbol de React).
 *  - El productor es `useChat` cuando recibe `progress_updated: true` desde
 *    `POST /chat`, o cualquier otro código que sepa que el progreso cambió.
 *  - El consumidor es `MaturityDashboard`, que se suscribe vía
 *    `useProgressUpdated(handler)` para re-disparar su fetch.
 *
 * Esta API es resiliente a SSR: tanto el dispatcher como el hook hacen
 * comprobación defensiva de `typeof window !== "undefined"` para no romper
 * el render server-side de Next.js App Router.
 */
export const PROGRESS_UPDATED_EVENT = "cotutor:progress-updated" as const;

/**
 * Emite el evento global `cotutor:progress-updated`.
 * No-op en SSR (cuando `window` no existe).
 */
export function dispatchProgressUpdated(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(PROGRESS_UPDATED_EVENT));
}

/**
 * Suscribe `handler` al evento global de progreso actualizado durante el
 * ciclo de vida del componente. El listener se reemplaza si `handler` cambia
 * de identidad (incluir el handler en `useCallback` evita re-suscripciones
 * innecesarias).
 */
export function useProgressUpdated(handler: () => void): void {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const listener = () => handler();
    window.addEventListener(PROGRESS_UPDATED_EVENT, listener);
    return () => {
      window.removeEventListener(PROGRESS_UPDATED_EVENT, listener);
    };
  }, [handler]);
}

// ---------------------------------------------------------------------------
// Acciones de chat desacopladas (cuadrante → chatbot)
// ---------------------------------------------------------------------------

export const LAUNCH_CHAT_ACTION_EVENT = "cotutor:launch-chat-action" as const;

/** Payload de una acción de chat lanzada desde el cuadrante u otros módulos. */
export type ChatActionDetail = {
  prompt: string;
  learning_unit_id?: number;
  unit_name?: string;
  unit_definition?: string;
};

/**
 * Emite una orden de chat (p. ej. generar cuestionario desde el cuadrante).
 * El consumidor es `ChatInputBar` vía `useChatAction`.
 */
export function dispatchChatAction(detail: ChatActionDetail | string): void {
  if (typeof window === "undefined") return;
  const payload: ChatActionDetail =
    typeof detail === "string" ? { prompt: detail } : detail;
  if (!payload.prompt?.trim()) return;
  window.dispatchEvent(
    new CustomEvent(LAUNCH_CHAT_ACTION_EVENT, { detail: payload }),
  );
}

/** Prompt y metadatos para solicitar un cuestionario exclusivo de una unidad. */
export function buildUnitQuizAction(
  unitId: number,
  unitName: string,
  unitDefinition: string,
): ChatActionDetail {
  return {
    learning_unit_id: unitId,
    unit_name: unitName,
    unit_definition: unitDefinition,
    prompt: `Genera un cuestionario escrito de nivel adaptativo EXCLUSIVAMENTE sobre esta unidad de aprendizaje.
Tema: ${unitName}
Enfoque obligatorio: ${unitDefinition}
Incluye preguntas de opción múltiple (A-D) y de desarrollo breve.
NO incluyas soluciones ni clave de respuestas.
No incluyas contenido de otras unidades del curso.
Indica al final que puedo enviar mis respuestas por chat para que las corrijas.`,
  };
}

/**
 * Suscribe `handler` al evento global de acción de chat.
 */
export function useChatAction(handler: (detail: ChatActionDetail) => void): void {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const listener = (e: Event) => {
      const customEvent = e as CustomEvent<ChatActionDetail>;
      const detail = customEvent.detail;
      if (detail?.prompt?.trim()) handler(detail);
    };
    window.addEventListener(LAUNCH_CHAT_ACTION_EVENT, listener);
    return () => {
      window.removeEventListener(LAUNCH_CHAT_ACTION_EVENT, listener);
    };
  }, [handler]);
}
