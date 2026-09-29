"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ArrowUp, Loader2, Square } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatComposerProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  isLoading: boolean;
  isStreaming?: boolean;
}

export function ChatComposer({ onSend, onStop, isLoading, isStreaming }: ChatComposerProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 250)}px`;
    }
  }, [input]);

  // Focus textarea when not loading
  useEffect(() => {
    if (!isLoading && !isStreaming) {
      // Small timeout ensures layout is done before focusing
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 50);
    }
  }, [isLoading, isStreaming]);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const showStopButton = isStreaming && onStop;
  const isSendDisabled = !input.trim() || isLoading;

  return (
    <div className="mx-auto w-full max-w-3xl">
      <div className="relative flex flex-col rounded-[1.25rem] border border-[var(--border)] bg-[var(--card)] px-4 py-3.5 shadow-sm transition-all focus-within:shadow-md focus-within:border-primary/30">
        <Textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about your enterprise knowledge..."
          className="min-h-[24px] max-h-[250px] w-full resize-none border-0 bg-transparent p-0 pr-12 focus-visible:ring-0 text-[0.9375rem] leading-relaxed placeholder:text-[var(--muted-foreground)]"
          rows={1}
          disabled={isLoading && !isStreaming}
        />
        
        <div className="absolute bottom-3 right-3 flex items-center justify-end">
          {showStopButton ? (
            <Button
              size="icon"
              onClick={(e) => {
                e.preventDefault();
                onStop();
              }}
              className="h-8 w-8 rounded-full bg-foreground text-background hover:bg-foreground/90 transition-all shadow-sm scale-in"
              aria-label="Stop generation"
            >
              <Square className="h-3 w-3 fill-current" />
            </Button>
          ) : (
            <Button
              size="icon"
              onClick={handleSend}
              disabled={isSendDisabled}
              className={cn(
                "h-8 w-8 rounded-full transition-all duration-200",
                !isSendDisabled 
                  ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm hover:shadow" 
                  : "bg-muted text-muted-foreground/50 opacity-60 shadow-none"
              )}
              aria-label="Send message"
            >
              {isLoading && !isStreaming ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowUp className="h-4 w-4" />
              )}
            </Button>
          )}
        </div>
      </div>
      <div className="mt-2 text-center text-xs text-muted-foreground">
        AI can make mistakes. Verify important information.
      </div>
    </div>
  );
}
