"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { api, ApiError, NetworkError } from "@/lib/api";
import { Source } from "@/lib/types";
import { UserMessage, AssistantMessage, TypingIndicator } from "./messages";
import { ChatComposer } from "./chat-composer";
import { useToast } from "@/components/ui/use-toast";
import { FileText, Search, Settings2, Mail } from "lucide-react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

import { AgentActivityData } from "./agent-activity";
import { ApprovalData } from "./approvals";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  agentActivity?: AgentActivityData[];
  approvalRequest?: ApprovalData;
  isStreaming?: boolean;
  activityLabel?: string;
};

// ─── Suggestions for Empty State ──────────────────────────
const SUGGESTIONS = [
  {
    icon: Search,
    title: "Search policies",
    prompt: "What is the annual leave policy and how do I apply for it?",
  },
  {
    icon: FileText,
    title: "Summarize a document",
    prompt: "Can you summarize the engineering onboarding guide?",
  },
  {
    icon: Settings2,
    title: "Compare policies",
    prompt: "What is the difference between the remote work policy and the hybrid work policy?",
  },
  {
    icon: Mail,
    title: "Draft an email",
    prompt: "Draft an email to my manager requesting time off next week.",
  },
];

export function ChatWindow({ conversationId }: { conversationId?: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Track the current conversation id internally so handleSend can read it
  // even when it was just created mid-flight (avoids stale closure issues).
  const activeConvIdRef = useRef<string | undefined>(conversationId);
  const { toast } = useToast();
  const router = useRouter();

  // Keep the ref in sync with the prop
  useEffect(() => {
    activeConvIdRef.current = conversationId;
  }, [conversationId]);

  // ─── Load existing messages ─────────────────────────────────────────────────
  useEffect(() => {
    if (conversationId) {
      api.conversations.get(conversationId).then((data) => {
        const mappedMessages: Message[] = data.messages.map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          content: m.content,
          sources: m.metadata?.sources as Source[] | undefined,
          agentActivity: m.metadata?.agent_activity as AgentActivityData[] | undefined,
          approvalRequest: m.metadata?.approval_request as ApprovalData | undefined,
          isStreaming: false,
        }));
        setMessages(mappedMessages);
      }).catch(() => {
        toast({
          title: "Failed to load conversation",
          description: "Could not load messages. The conversation may have been deleted.",
          variant: "destructive",
        });
        router.push("/");
      });
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMessages([]);
    }
  }, [conversationId, toast, router]);

  // ─── Auto-scroll ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 200;
    if (isNearBottom || isStreaming) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, isStreaming]);

  // ─── Stop generation ────────────────────────────────────────────────────────
  const handleStop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  // ─── Show a descriptive toast for API/network errors ────────────────────────
  const showErrorToast = useCallback(
    (err: unknown) => {
      if (err instanceof DOMException && err.name === "AbortError") return; // user-cancelled
      if (err instanceof ApiError) {
        toast({
          title: `${err.label} (${err.status})`,
          description: err.message,
          variant: "destructive",
        });
      } else if (err instanceof NetworkError) {
        toast({
          title: "Network error",
          description: err.message,
          variant: "destructive",
        });
      } else {
        toast({
          title: "Unexpected error",
          description: String(err),
          variant: "destructive",
        });
      }
    },
    [toast]
  );

  // ─── Core send handler ──────────────────────────────────────────────────────
  const handleSend = useCallback(
    async (question: string) => {
      if (isLoading) return; // prevent double-fire

      // Add user message immediately
      const userMsgId = `user-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: userMsgId, role: "user", content: question },
      ]);
      setIsLoading(true);

      // ── Ensure we have a conversation ──────────────────────────────────────
      let targetId = activeConvIdRef.current;
      if (!targetId) {
        try {
          const conv = await api.conversations.create();
          targetId = conv.id;
          activeConvIdRef.current = targetId;
          // Update URL without triggering Next.js re-mount
          window.history.replaceState(null, "", `/chat/${targetId}`);
          window.dispatchEvent(new Event("conversationCreated"));
        } catch (err) {
          showErrorToast(err);
          setIsLoading(false);
          return;
        }
      }

      // ── Add a placeholder assistant message that will be streamed into ─────
      const assistantMsgId = `assistant-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMsgId,
          role: "assistant",
          content: "",
          isStreaming: true,
          activityLabel: "Thinking...",
        },
      ]);

      // ── Open abort controller for Stop Generation ──────────────────────────
      const controller = new AbortController();
      abortRef.current = controller;
      setIsStreaming(true);

      let sources: Source[] = [];

      try {
        const stream = api.conversations.streamMessage(
          targetId,
          question,
          controller.signal
        );

        for await (const event of stream) {
          if (event.type === "activity") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, activityLabel: event.content }
                  : m
              )
            );
          } else if (event.type === "token") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      content: m.content + event.content,
                      activityLabel: undefined,
                    }
                  : m
              )
            );
          } else if (event.type === "approval") {
            // Agent is waiting for human approval — attach approval data so the card renders
            try {
              const approvalData = JSON.parse(event.content) as ApprovalData;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsgId
                    ? { ...m, approvalRequest: approvalData, isStreaming: false, activityLabel: undefined }
                    : m
                )
              );
            } catch {
              // ignore parse errors
            }
          } else if (event.type === "done") {
            sources = event.sources ?? [];
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, sources, isStreaming: false, activityLabel: undefined }
                  : m
              )
            );
          } else if (event.type === "error") {
            toast({
              title: "Generation error",
              description: event.detail,
              variant: "destructive",
            });
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, isStreaming: false, activityLabel: undefined }
                  : m
              )
            );
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // User stopped — finalise current content
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, isStreaming: false, activityLabel: undefined }
                : m
            )
          );
        } else {
          showErrorToast(err);
          // Remove the empty placeholder on total failure
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content: m.content || "(No response)", isStreaming: false, activityLabel: undefined }
                : m
            )
          );
        }
      } finally {
        abortRef.current = null;
        setIsLoading(false);
        setIsStreaming(false);
      }
    },
    [isLoading, showErrorToast, toast]
  );

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-full flex-col relative bg-[var(--background)]">
      {/* Messages area */}
      <div
        className="flex-1 overflow-y-auto px-4 pb-32 pt-8 scroll-smooth"
        ref={scrollRef}
      >
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
          {isEmpty ? (
            <div className="flex flex-col items-center justify-center pt-[15vh] pb-8 animate-fade-in">
              <div className="mb-8 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm ring-1 ring-primary/10">
                <Search className="h-6 w-6" />
              </div>
              <h1 className="mb-2 text-2xl font-medium tracking-tight text-foreground">
                How can I help you today?
              </h1>
              <p className="mb-10 text-center text-sm text-muted-foreground max-w-[420px]">
                Search enterprise knowledge, compare policies, or run agent workflows.
              </p>

              <div className="grid w-full max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => !isLoading && handleSend(s.prompt)}
                    disabled={isLoading}
                    className={cn(
                      "group flex flex-col items-start gap-2 rounded-xl border border-border bg-card p-5 text-left transition-all hover:bg-accent/50 hover:shadow-sm hover:border-border/80 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50 disabled:cursor-not-allowed",
                      `stagger-${i + 1} animate-slide-up`
                    )}
                  >
                    <div className="flex items-center gap-2 text-sm font-medium text-foreground transition-colors group-hover:text-primary">
                      <s.icon className="h-4 w-4 text-primary/80 transition-transform group-hover:scale-110" />
                      {s.title}
                    </div>
                    <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                      &quot;{s.prompt}&quot;
                    </p>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((m) =>
                m.role === "user" ? (
                  <UserMessage key={m.id} content={m.content} />
                ) : (
                  <AssistantMessage
                    key={m.id}
                    content={m.content}
                    sources={m.sources}
                    agentActivity={m.agentActivity}
                    approvalRequest={m.approvalRequest}
                    isStreaming={m.isStreaming}
                    activityLabel={m.activityLabel}
                  />
                )
              )}
              {isLoading && !isStreaming && (
                <TypingIndicator label="Processing request" />
              )}
            </>
          )}
        </div>
      </div>

      {/* Composer area - Fixed at bottom */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-background via-background/95 to-transparent pb-6 pt-10 px-4">
        <ChatComposer
          onSend={handleSend}
          onStop={handleStop}
          isLoading={isLoading}
          isStreaming={isStreaming}
        />
      </div>
    </div>
  );
}
