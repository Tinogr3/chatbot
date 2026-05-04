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
