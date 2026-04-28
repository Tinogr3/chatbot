"use client";

import { useCallback, useState } from "react";
import LeftSidebar from "@/components/LeftSidebar";
import MainContent from "@/components/MainContent";
import ChatPanel from "@/components/ChatPanel";
import { WelcomeScreen } from "@/components/auth/WelcomeScreen";
import { useChat } from "@/hooks/useChat";
import { UserProvider, useUser } from "@/context/UserContext";
import { ProjectsProvider, useProjects } from "@/context/ProjectsContext";
import { dictionaries } from "@/locales";

export default function DashboardPage() {
  return (
    <UserProvider>
      <ProjectsProvider>
        <DashboardGate />
      </ProjectsProvider>
    </UserProvider>
  );
}

function FullscreenLoading() {
  return (
    <div className="min-h-screen w-full bg-gray-50 flex items-center justify-center">
      <div className="text-gray-500 text-sm">{dictionaries.common.loading}</div>
    </div>
  );
}

function DashboardGate() {
  const { sessionId, isHydrated } = useUser();

  if (!isHydrated) return <FullscreenLoading />;
  if (!sessionId) return <WelcomeScreen />;

  return <DashboardLayout />;
}

function DashboardLayout() {
  const { sessionId } = useUser();
  const { effectiveSessionId, isHydrated: projectsHydrated } = useProjects();
  const { messages, isLoading, error, sendMessage, isLearningMode, toggleLearningMode } = useChat({
    sessionId: effectiveSessionId ?? undefined,
  });
  const [isChatExpanded, setIsChatExpanded] = useState(false);
  const toggleChatExpanded = useCallback(() => setIsChatExpanded((prev) => !prev), []);

  if (!sessionId) return null;
  if (!projectsHydrated || !effectiveSessionId) return <FullscreenLoading />;

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
        isExpanded={isChatExpanded}
        onToggleExpand={toggleChatExpanded}
        onSendMessage={sendMessage}
        isLearningMode={isLearningMode}
        onToggleLearningMode={toggleLearningMode}
      />
    </div>
  );
}
