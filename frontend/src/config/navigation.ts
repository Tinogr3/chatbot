"use client";

import type { ComponentType } from "react";
import { BookOpen, Library, Mic, Scale } from "lucide-react";

export type NavItem = {
  label: string;
  active: boolean;
  badge: string | null;
  icon: ComponentType<{ className?: string }>;
};

export const navItems: NavItem[] = [
  {
    label: "BIBLIOTECA DE CONOCIMIENTO",
    active: true,
    badge: null,
    icon: Library,
  },
  {
    label: "Manuales Internos",
    active: false,
    badge: "OFICIAL",
    icon: BookOpen,
  },
  {
    label: "Regulaciones Legales",
    active: false,
    badge: "VERIFICADO",
    icon: Scale,
  },
  {
    label: "Grabaciones de Expertos",
    active: false,
    badge: null,
    icon: Mic,
  },
];

