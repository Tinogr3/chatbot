"use client";

import type { ComponentType } from "react";
import { FileQuestion, Mic, MessageSquare, Video } from "lucide-react";
import { dictionaries } from "@/locales";

const tCategories = dictionaries.dashboard.categories;
const tCriteria = dictionaries.dashboard.learningCriteria;
const tCards = dictionaries.mainContent.contentCards;

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
  { name: tCategories.dataSovereignty, percent: 82 },
  { name: tCategories.privacyArchitecture, percent: 45 },
  { name: tCategories.aiEthics, percent: 68 },
];

export type DashboardIcon = ComponentType<{ className?: string }>;

export type ContentCard = {
  title: string;
  count: number;
  icon: DashboardIcon;
};

export const contentCards: ContentCard[] = [
  { title: tCards.videoPills, count: 3, icon: Video as DashboardIcon },
  { title: tCards.podcasts, count: 5, icon: Mic as DashboardIcon },
  { title: tCards.summaries, count: 12, icon: MessageSquare as DashboardIcon },
  { title: tCards.exams, count: 8, icon: FileQuestion as DashboardIcon },
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
    name: tCriteria.dataGovernance.name,
    description: tCriteria.dataGovernance.description,
    domainPercent: 85,
    grade: "A",
    category: tCategories.dataSovereignty,
  },
  {
    id: "crit-2",
    name: tCriteria.privacyByDesign.name,
    description: tCriteria.privacyByDesign.description,
    domainPercent: 52,
    grade: "C",
    category: tCategories.privacyArchitecture,
  },
  {
    id: "crit-3",
    name: tCriteria.algorithmicBias.name,
    description: tCriteria.algorithmicBias.description,
    domainPercent: 68,
    grade: "B",
    category: tCategories.aiEthics,
  },
];
