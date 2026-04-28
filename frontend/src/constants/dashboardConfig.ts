"use client";

import type { ComponentType } from "react";
import { FileQuestion, Mic, MessageSquare, Video } from "lucide-react";

export const HEATMAP_LEVELS: number[][] = [
  [4, 3, 2, 4, 5, 3, 4, 2, 3, 4],
  [2, 4, 5, 3, 4, 5, 2, 4, 3, 5],
  [3, 2, 4, 5, 3, 4, 5, 2, 4, 3],
  [5, 4, 3, 2, 4, 3, 4, 5, 3, 4],
  [4, 5, 4, 4, 2, 5, 3, 4, 5, 2],
];

export type DashboardCategory = {
  name: string;
  percent: number;
};

export const categories: DashboardCategory[] = [
  { name: "Soberanía de Datos", percent: 82 },
  { name: "Arquitectura Privacidad", percent: 45 },
  { name: "Ética en IA", percent: 68 },
];

export type DashboardIcon = ComponentType<{ className?: string }>;

export type ContentCard = {
  title: string;
  count: number;
  icon: DashboardIcon;
};

export const contentCards: ContentCard[] = [
  { title: "Video Píldoras", count: 3, icon: Video as DashboardIcon },
  { title: "Podcasts", count: 5, icon: Mic as DashboardIcon },
  { title: "Resúmenes", count: 12, icon: MessageSquare as DashboardIcon },
  { title: "Exámenes", count: 8, icon: FileQuestion as DashboardIcon },
];

export type GradeLevel = "A" | "B" | "C" | "D";

export type LearningCriterion = {
  id: string;
  name: string;
  description: string;
  domainPercent: number;
  grade: GradeLevel;
  category: string;
};

export const learningCriteria: LearningCriterion[] = [
  {
    id: "crit-1",
    name: "Gobernanza de Datos",
    description:
      "Capacidad para diseñar políticas de gobernanza y ciclo de vida del dato.",
    domainPercent: 85,
    grade: "A",
    category: "Soberanía de Datos",
  },
  {
    id: "crit-2",
    name: "Privacy by Design",
    description:
      "Aplicación de principios de privacidad desde la fase de diseño de sistemas.",
    domainPercent: 52,
    grade: "C",
    category: "Arquitectura Privacidad",
  },
  {
    id: "crit-3",
    name: "Sesgo Algorítmico",
    description:
      "Identificación y mitigación de sesgos en modelos de IA y pipelines de datos.",
    domainPercent: 68,
    grade: "B",
    category: "Ética en IA",
  },
];

