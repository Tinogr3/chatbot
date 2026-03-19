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

