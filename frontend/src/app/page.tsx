"use client";

import LeftSidebar from "@/components/LeftSidebar";
import MainContent from "@/components/MainContent";
import ChatPanel from "@/components/ChatPanel";
import { useChat } from "@/hooks/useChat";

export default function DashboardPage() {
  const { messages, isLoading, error, sendMessage } = useChat({
    sessionId: "alex_rivera",
  });

  return (
    <div className="flex h-screen w-full bg-gray-50 overflow-hidden">
      <LeftSidebar />
      <MainContent onSendMessage={sendMessage} />
      <ChatPanel messages={messages} isLoading={isLoading} error={error} />
    </div>
  );
}
