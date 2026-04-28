"use client";

import { Maximize2, Minimize2 } from "lucide-react";
import { dictionaries } from "@/locales";

const t = dictionaries.chatPanel.expandButton;

export type ExpandToggleButtonProps = {
  isExpanded: boolean;
  onToggle: () => void;
};

export default function ExpandToggleButton({
  isExpanded,
  onToggle,
}: ExpandToggleButtonProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      title={isExpanded ? t.collapse : t.expand}
      className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
    >
      {isExpanded ? (
        <Minimize2 className="w-4 h-4" />
      ) : (
        <Maximize2 className="w-4 h-4" />
      )}
    </button>
  );
}
