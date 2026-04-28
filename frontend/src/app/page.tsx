"use client";

import { useCallback, useState } from "react";
import LeftSidebar from "@/components/LeftSidebar";
import MainContent from "@/components/MainContent";
import ChatPanel from "@/components/ChatPanel";
import { WelcomeScreen } from "@/components/auth/WelcomeScreen";
import { useChat } from "@/hooks/useChat";
import { UserProvider, useUser } from "@/context/UserContext";

export default function DashboardPage() {
  return (
    <UserProvider>
      <DashboardGate />
    </UserProvider>
  );
}

function DashboardGate() {
  const { sessionId, isHydrated } = useUser();

  if (!isHydrated) {
    return (
      <div className="min-h-screen w-full bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500 text-sm">Cargando...</div>
      </div>
    );
  }

  if (!sessionId) return <WelcomeScreen />;

  return <DashboardLayoutWithLogout />;
}

function DashboardLayoutWithLogout() {
  const { sessionId } = useUser();
  const { messages, isLoading, error, sendMessage, isLearningMode, toggleLearningMode } = useChat({
    sessionId: sessionId ?? undefined,
  });
  const [isChatExpanded, setIsChatExpanded] = useState(false);
  const toggleChatExpanded = useCallback(() => setIsChatExpanded((prev) => !prev), []);

  if (!sessionId) return null;

  return (
    <div className="flex h-screen w-full bg-gray-50 overflow-hidden">
      {!isChatExpanded && <LeftSidebar />}
      <MainContent
        onSendMessage={sendMessage}
        hidden={isChatExpanded}
        isLearningMode={isLearningMode}
        onToggleLearningMode={toggleLearningMode}
      />
      <ChatPanel
        messages={messages}
        isLoading={isLoading}
        error={error}
        scaffoldMessage="La IA está guiando tu razonamiento hacia la Arquitectura de Privacidad."
        isExpanded={isChatExpanded}
        onToggleExpand={toggleChatExpanded}
      />
    </div>
  );
}
