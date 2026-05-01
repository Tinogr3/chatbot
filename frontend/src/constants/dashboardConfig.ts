"use client";

import type { ComponentType } from "react";
import { FileQuestion, Mic, MessageSquare } from "lucide-react";
import { dictionaries } from "@/locales";

const tCards = dictionaries.mainContent.contentCards;

export type DashboardIcon = ComponentType<{ className?: string }>;

export type ContentCard = {
  title: string;
  count: number;
  icon: DashboardIcon;
};

export const contentCards: ContentCard[] = [
  { title: tCards.podcasts, count: 5, icon: Mic as DashboardIcon },
  { title: tCards.summaries, count: 12, icon: MessageSquare as DashboardIcon },
  { title: tCards.exams, count: 8, icon: FileQuestion as DashboardIcon },
];
