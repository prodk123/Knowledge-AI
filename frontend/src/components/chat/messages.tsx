"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Components } from "react-markdown";
import { useState, useCallback } from "react";
import { FileText, Copy, Check, ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import { Source } from "@/lib/types";
import { cn } from "@/lib/utils";
import SyntaxHighlighter from "react-syntax-highlighter";
import { oneLight, oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useTheme } from "next-themes";
import { AgentActivity, AgentActivityData } from "./agent-activity";
import { ApprovalCard, ApprovalData } from "./approvals";

// ─── Source card ──────────────────────────────────────────
export function SourceCard({ source, index }: { source: Source; index: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-border bg-card text-[0.8125rem] overflow-hidden transition-all hover:shadow-sm">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-3 px-3.5 py-3 text-left hover:bg-muted/30 transition-colors"
      >
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-primary/10 font-semibold text-primary">
          {index + 1}
        </span>
        <FileText className="h-4 w-4 shrink-0 text-muted-foreground/70" />
        <span className="flex-1 truncate font-medium text-foreground">{source.filename}</span>
        {source.page_number && (
          <span className="text-muted-foreground shrink-0 font-medium bg-muted px-1.5 py-0.5 rounded-md">p. {source.page_number}</span>
        )}
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
        )}
      </button>

      {expanded && source.text && (
        <div className="border-t border-border/50 px-3.5 py-3 bg-muted/10">
          <p className="text-muted-foreground line-clamp-6 leading-relaxed whitespace-pre-wrap">{source.text}</p>
        </div>
      )}
    </div>
  );
}

// ─── Sources section ──────────────────────────────────────
export function SourcesSection({ sources }: { sources: Source[] }) {
  const [expanded, setExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-5 border-t border-border/50 pt-4">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="group flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors mb-3"
        aria-expanded={expanded}
      >
        {expanded ? <ChevronDown className="h-3.5 w-3.5 transition-transform" /> : <ChevronRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />}
        <span className="tracking-wide uppercase">Sources</span>
        <span className="flex h-4 min-w-[1.25rem] items-center justify-center rounded-full bg-muted/80 px-1 text-[10px] font-medium text-foreground">
          {sources.length}
        </span>
      </button>

      {expanded && (
        <div className="grid gap-2 sm:grid-cols-2 animate-fade-in">
          {sources.map((source, i) => (
            <SourceCard key={source.chunk_id ?? i} source={source} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Code block ───────────────────────────────────────────
function CodeBlock({
  language,
  children,
}: {
  language: string;
  children: string;
}) {
  const [copied, setCopied] = useState(false);
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(children).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [children]);

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-[var(--code-border)]">
      {/* Header */}
      <div className="flex items-center justify-between bg-[var(--code-header-bg)] px-4 py-2">
        <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
          {language || "code"}
        </span>
        <button
          onClick={handleCopy}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium transition-all",
            copied
              ? "text-[var(--success)] bg-[var(--success)]/10"
              : "text-muted-foreground hover:text-foreground hover:bg-background/40"
          )}
          aria-label={copied ? "Copied!" : "Copy code"}
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>

      {/* Code content */}
      <SyntaxHighlighter
        language={language || "text"}
        style={isDark ? oneDark : oneLight}
        customStyle={{
          margin: 0,
          padding: "1rem",
          background: "var(--code-bg)",
          fontSize: "0.8125rem",
          lineHeight: "1.6",
        }}
        wrapLongLines={false}
        showLineNumbers={children.split("\n").length > 8}
      >
        {children}
      </SyntaxHighlighter>
    </div>
  );
}

// ─── Markdown components ──────────────────────────────────
function buildMarkdownComponents(): Components {
  return {
    code(props) {
      const { className, children, ...rest } = props;
      const match = /language-(\w+)/.exec(className || "");
      const isInline = !match;
      const code = String(children).replace(/\n$/, "");

      if (isInline) {
        return (
          <code
            className="rounded bg-[var(--code-bg)] border border-[var(--code-border)] px-1.5 py-0.5 font-mono text-[0.84em]"
            {...rest}
          >
            {children}
          </code>
        );
      }

      return <CodeBlock language={match[1]}>{code}</CodeBlock>;
    },

    // Tables with horizontal scroll
    table({ children }) {
      return (
        <div className="my-3 w-full overflow-x-auto rounded-xl border border-border">
          <table className="min-w-full text-sm">{children}</table>
        </div>
      );
    },
    thead({ children }) {
      return <thead className="bg-muted/60">{children}</thead>;
    },
    th({ children }) {
      return (
        <th className="px-4 py-2.5 text-left text-xs font-semibold text-foreground border-b border-border">
          {children}
        </th>
      );
    },
    td({ children }) {
      return (
        <td className="px-4 py-2.5 text-sm border-b border-border/50 last:border-b-0">
          {children}
        </td>
      );
    },
    tr({ children }) {
      return (
        <tr className="hover:bg-muted/30 transition-colors">{children}</tr>
      );
    },

    // Blockquote
    blockquote({ children }) {
      return (
        <blockquote className="my-3 border-l-[3px] border-primary/40 pl-4 text-muted-foreground italic">
          {children}
        </blockquote>
      );
    },

    // Links — open external in new tab
    a({ href, children }) {
      const isExternal = href?.startsWith("http");
      return (
        <a
          href={href}
          target={isExternal ? "_blank" : undefined}
          rel={isExternal ? "noopener noreferrer" : undefined}
          className="text-primary underline underline-offset-2 hover:opacity-80 transition-opacity inline-flex items-center gap-0.5"
        >
          {children}
          {isExternal && <ExternalLink className="h-3 w-3 inline" />}
        </a>
      );
    },

    // Headings
    h1({ children }) { return <h1 className="text-xl font-semibold mt-6 mb-3 text-foreground tracking-tight">{children}</h1>; },
    h2({ children }) { return <h2 className="text-lg font-semibold mt-5 mb-3 text-foreground tracking-tight">{children}</h2>; },
    h3({ children }) { return <h3 className="text-base font-semibold mt-4 mb-2 text-foreground">{children}</h3>; },
    h4({ children }) { return <h4 className="text-sm font-semibold mt-3 mb-2 text-foreground">{children}</h4>; },

    // Lists
    ul({ children }) { return <ul className="my-4 ml-6 space-y-2 list-disc marker:text-muted-foreground">{children}</ul>; },
    ol({ children }) { return <ol className="my-4 ml-6 space-y-2 list-decimal marker:text-muted-foreground">{children}</ol>; },
    li({ children }) { return <li className="text-[0.9375rem] leading-7 text-foreground pl-1">{children}</li>; },

    p({ children }) {
      return <p className="mb-4 last:mb-0 text-[0.9375rem] leading-7 text-foreground">{children}</p>;
    },
    hr() { return <hr className="my-6 border-border/60" />; },
  };
}

// ─── Typing / processing indicator ────────────────────────
export function TypingIndicator({ label = "Preparing response" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-4 animate-fade-in">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">{label}</span>
        <div className="flex gap-1">
          <span
            className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60"
            style={{ animation: "pulse-dot 1.2s ease-in-out infinite", animationDelay: "0ms" }}
          />
          <span
            className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60"
            style={{ animation: "pulse-dot 1.2s ease-in-out infinite", animationDelay: "200ms" }}
          />
          <span
            className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60"
            style={{ animation: "pulse-dot 1.2s ease-in-out infinite", animationDelay: "400ms" }}
          />
        </div>
      </div>
    </div>
  );
}

// ─── User message ─────────────────────────────────────────
export function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end animate-fade-in mb-2">
      <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-muted/60 px-4 py-3 text-foreground shadow-sm">
        <p className="text-[0.9375rem] leading-relaxed whitespace-pre-wrap">{content}</p>
      </div>
    </div>
  );
}

// ─── Assistant message ────────────────────────────────────
export function AssistantMessage({
  content,
  sources,
  isStreaming,
  agentActivity,
  approvalRequest,
  activityLabel,
}: {
  content: string;
  sources?: Source[];
  isStreaming?: boolean;
  agentActivity?: AgentActivityData[];
  approvalRequest?: ApprovalData;
  activityLabel?: string;
}) {
  const [copied, setCopied] = useState(false);
  const markdownComponents = buildMarkdownComponents();

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [content]);

  return (
    <div className="group flex gap-3 animate-fade-in">
      {/* Avatar */}
      <div className="flex h-7 w-7 shrink-0 mt-0.5 items-center justify-center rounded-full bg-primary/10 text-primary ring-1 ring-primary/20">
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        
        {/* Agent Activity */}
        {agentActivity && agentActivity.length > 0 && (
          <AgentActivity activities={agentActivity} />
        )}
        
        {/* Markdown body (only render if there's content) */}
        {activityLabel && !content && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground animate-pulse">
            <span>{activityLabel}</span>
          </div>
        )}
        {content && (
          <div className="prose-message">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {content}
            </ReactMarkdown>
            {isStreaming && (
              <span className="inline-block w-0.5 h-4 bg-foreground ml-0.5 animate-cursor-blink align-middle" />
            )}
          </div>
        )}

        {/* Approval Card */}
        {approvalRequest && (
          <ApprovalCard approval={approvalRequest} />
        )}

        {/* Sources */}
        {!isStreaming && sources && sources.length > 0 && (
          <SourcesSection sources={sources} />
        )}

        {/* Message actions — show on hover when complete */}
        {!isStreaming && content && (
          <div className="mt-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
            <button
              onClick={handleCopy}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-all",
                copied
                  ? "text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )}
              aria-label={copied ? "Copied" : "Copy message"}
            >
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
