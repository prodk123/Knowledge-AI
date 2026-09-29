import { ChatWindow } from "@/components/chat/chat-window";

export default async function ConversationPage({ params }: { params: Promise<{ conversationId: string }> }) {
  const { conversationId } = await params;
  return <ChatWindow conversationId={conversationId} />;
}
