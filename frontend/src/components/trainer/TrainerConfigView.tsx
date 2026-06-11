"use client";

import { useState } from "react";
import type { GeneratedItinerary } from "@/lib/api";
import TrainerChat from "@/components/trainer/TrainerChat";
import QuadrantValidator from "@/components/trainer/QuadrantValidator";

export type TrainerConfigViewProps = {
  /** Notifica al contenedor que se guardó un itinerario (para refrescar el progreso). */
  onItinerarySaved?: () => void;
};

/**
 * Vista de configuración del formador (split-pane):
 *   izquierda — chat IA conectado a /trainer/generate-itinerary;
 *   derecha   — validador/editor del cuadrante con guardado en BD.
 */
export default function TrainerConfigView({ onItinerarySaved }: TrainerConfigViewProps) {
  const [itinerary, setItinerary] = useState<GeneratedItinerary | null>(null);

  return (
    <div className="grid h-[calc(100vh-220px)] min-h-[420px] grid-cols-1 gap-4 lg:grid-cols-2">
      <TrainerChat onItineraryGenerated={setItinerary} />
      <QuadrantValidator itinerary={itinerary} onSaved={onItinerarySaved} />
    </div>
  );
}
