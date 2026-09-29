"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  FileText,
  Settings,
  Plus,
  Activity,
  LogOut,
  ChevronLeft,
  Trash2,
  Pencil,
  Check,
  X,
  Search,
  Menu,
  BrainCircuit,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Conversation } from "@/lib/types";
import { isToday, isYesterday, subDays, isAfter } from "date-fns";

// --- Conversation grouping ---
type ConversationGroup = {
  label: string;
  items: Conversation[];
};

function groupConversations(conversations: Conversation[]): ConversationGroup[] {
  const now = new Date();
  const groups: ConversationGroup[] = [
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Previous 7 days", items: [] },
    { label: "Previous 30 days", items: [] },
    { label: "Older", items: [] },
  ];

  for (const conv of conversations) {
    const d = new Date(conv.updated_at);
    if (isToday(d)) groups[0].items.push(conv);
    else if (isYesterday(d)) groups[1].items.push(conv);
    else if (isAfter(d, subDays(now, 7))) groups[2].items.push(conv);
    else if (isAfter(d, subDays(now, 30))) groups[3].items.push(conv);
    else groups[4].items.push(conv);
  }

  return groups.filter((g) => g.items.length > 0);
}

// --- Conversation item with inline rename/delete ---
function ConversationItem({
  conv,
  isActive,
  onRenamed,
  onDeleted,
  onNavigate,
}: {
  conv: Conversation;
  isActive: boolean;
  onRenamed: (id: string, title: string) => void;
  onDeleted: (id: string) => void;
  onNavigate?: () => void;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(conv.title);
  const renameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isRenaming) renameRef.current?.focus();
  }, [isRenaming]);

  const handleRename = async () => {
    if (!renameValue.trim() || renameValue === conv.title) {
      setIsRenaming(false);
      setRenameValue(conv.title);
      return;
    }
    try {
      await api.conversations.rename(conv.id, renameValue.trim());
      onRenamed(conv.id, renameValue.trim());
    } catch {
      setRenameValue(conv.title);
    }
    setIsRenaming(false);
  };

  const handleDelete = async () => {
    try {
      await api.conversations.delete(conv.id);
      onDeleted(conv.id);
    } catch {
      // ignore
    }
  };

  if (isRenaming) {
    return (
      <div className="flex items-center gap-1 rounded-lg px-2 py-1.5 bg-accent">
        <input
          ref={renameRef}
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleRename();
            if (e.key === "Escape") { setIsRenaming(false); setRenameValue(conv.title); }
          }}
          className="flex-1 min-w-0 bg-transparent text-sm text-foreground outline-none"
        />
        <button
          onClick={handleRename}
          className="text-muted-foreground hover:text-foreground transition-colors p-0.5"
          aria-label="Confirm rename"
        >
          <Check className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => { setIsRenaming(false); setRenameValue(conv.title); }}
          className="text-muted-foreground hover:text-foreground transition-colors p-0.5"
          aria-label="Cancel rename"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "group relative flex items-center rounded-lg transition-colors duration-150",
        isActive
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground hover:bg-sidebar-accent/60"
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <Link
        href={`/chat/${conv.id}`}
        onClick={onNavigate}
        className="flex-1 min-w-0 px-3 py-2 text-sm leading-snug truncate"
        title={conv.title}
      >
        {conv.title}
      </Link>

      {/* Contextual actions */}
      {(isHovered || isActive) && (
        <div className="flex items-center gap-0.5 pr-1.5 shrink-0">
          <button
            onClick={() => setIsRenaming(true)}
            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-background/40 transition-colors"
            aria-label="Rename conversation"
          >
            <Pencil className="h-3 w-3" />
          </button>
          <button
            onClick={handleDelete}
            className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
            aria-label="Delete conversation"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}

// --- Main Sidebar content ---
export function SidebarContent({
  collapsed,
  onToggleCollapse,
  onNavigate,
}: {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const { user, logout, hasPermission } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [search, setSearch] = useState("");
  // Prevent double-click on New Chat from firing multiple navigations
  const newChatPending = useRef(false);
  const router = useRouter();

  const loadConversations = useCallback(() => {
    if (user && hasPermission("chat.use")) {
      api.conversations.list().then(setConversations).catch(console.error);
    }
  }, [user, hasPermission]);

  useEffect(() => {
    loadConversations();
    
    const handleConvCreated = () => {
      loadConversations();
    };
    
    window.addEventListener("conversationCreated", handleConvCreated);
    return () => {
      window.removeEventListener("conversationCreated", handleConvCreated);
    };
  }, [loadConversations, pathname]);

  const handleNewChat = useCallback(() => {
    if (newChatPending.current) return; // guard against rapid clicks
    newChatPending.current = true;
    onNavigate?.();
    router.push("/");
    // Reset guard on next tick after navigation is dispatched
    setTimeout(() => { newChatPending.current = false; }, 300);
  }, [onNavigate, router]);

  const handleRenamed = (id: string, title: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title } : c))
    );
  };

  const handleDeleted = (id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
  };

  const filtered = search.trim()
    ? conversations.filter((c) =>
        c.title.toLowerCase().includes(search.toLowerCase())
      )
    : conversations;

  const grouped = search.trim()
    ? [{ label: "Results", items: filtered }]
    : groupConversations(filtered);

  const navItems = [
    { name: "Documents", href: "/documents", icon: FileText, permission: "documents.read" },
    { name: "Evaluation", href: "/evaluation", icon: Activity, permission: "evaluation.view" },
    { name: "Users", href: "/users", icon: Users, permission: "users.manage" },
  ];

  if (collapsed) {
    return (
      <div className="flex h-full flex-col items-center py-3 gap-1">
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
          aria-label="Expand sidebar"
        >
          <BrainCircuit className="h-5 w-5 text-primary" />
        </button>
        <div className="flex-1" />
        {hasPermission("chat.use") && (
          <button
            onClick={handleNewChat}
            className="p-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
            aria-label="New Chat"
          >
            <Plus className="h-4 w-4" />
          </button>
        )}
        {navItems.map((item) =>
          hasPermission(item.permission) ? (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn("p-2 rounded-lg transition-colors",
                pathname === item.href ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground"
              )}
              aria-label={item.name}
            >
              <item.icon className="h-4 w-4" />
            </Link>
          ) : null
        )}
        <Link href="/settings" onClick={onNavigate} className={cn("p-2 rounded-lg transition-colors", pathname === "/settings" ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-muted-foreground hover:bg-sidebar-accent")}>
          <Settings className="h-4 w-4" />
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Brand header */}
      <div className="flex h-14 items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <BrainCircuit className="h-4 w-4 text-primary-foreground" />
          </div>
          <span className="font-semibold text-sm tracking-tight text-sidebar-foreground">Knowledge AI</span>
        </div>
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-md text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
            aria-label="Collapse sidebar"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* New Chat */}
      {hasPermission("chat.use") && (
        <div className="px-3 pb-2 shrink-0">
          <button
            onClick={handleNewChat}
            className="flex w-full items-center gap-2 rounded-lg bg-primary/10 px-3 py-2 text-sm font-medium text-primary hover:bg-primary/20 active:scale-[0.98] transition-all"
          >
            <Plus className="h-4 w-4" />
            New chat
          </button>
        </div>
      )}

      {/* Search */}
      {hasPermission("chat.use") && conversations.length > 0 && (
        <div className="px-3 pb-2 shrink-0">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search conversations..."
              className="w-full rounded-md border border-sidebar-border bg-background/60 py-1.5 pl-8 pr-3 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring transition-colors"
            />
          </div>
        </div>
      )}

      {/* Conversations list */}
      <div className="flex-1 overflow-y-auto px-3 pb-2">
        {hasPermission("chat.use") && grouped.length > 0 && (
          <div className="space-y-4">
            {grouped.map((group) => (
              <div key={group.label}>
                <p className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                  {group.label}
                </p>
                <div className="space-y-0.5">
                  {group.items.map((conv) => (
                    <ConversationItem
                      key={conv.id}
                      conv={conv}
                      isActive={pathname === `/chat/${conv.id}`}
                      onRenamed={handleRenamed}
                      onDeleted={handleDeleted}
                      onNavigate={onNavigate}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
        {hasPermission("chat.use") && search && filtered.length === 0 && (
          <p className="px-2 py-3 text-xs text-muted-foreground">No conversations found.</p>
        )}

        {/* Workspace nav */}
        {navItems.some((item) => hasPermission(item.permission)) && (
          <div className="mt-4 border-t border-sidebar-border/60 pt-4">
            <p className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
              Workspace
            </p>
            <div className="space-y-0.5">
              {navItems.map((item) =>
                hasPermission(item.permission) ? (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                      pathname === item.href
                        ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                        : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.name}
                  </Link>
                ) : null
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer: settings + user */}
      <div className="shrink-0 border-t border-sidebar-border/60 p-3 space-y-1">
        <Link
          href="/settings"
          onClick={onNavigate}
          className={cn(
            "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
            pathname === "/settings"
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
          )}
        >
          <Settings className="h-4 w-4" />
          Settings
        </Link>

        {user && (
          <div className="flex items-center gap-2.5 rounded-lg px-3 py-2">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-semibold">
              {user.full_name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium leading-none truncate text-sidebar-foreground">{user.full_name}</p>
              <p className="text-[11px] text-muted-foreground truncate mt-0.5">
                {user.roles.map((r) => r.name).join(", ")}
              </p>
            </div>
            <button
              onClick={logout}
              className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors shrink-0"
              aria-label="Sign out"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// --- Desktop sidebar with collapse ---
export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className={cn(
        "flex h-full flex-col border-r border-sidebar-border bg-sidebar transition-all duration-300 ease-in-out",
        collapsed ? "w-14" : "w-60"
      )}
    >
      <SidebarContent
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((v) => !v)}
      />
    </div>
  );
}

// --- Mobile nav ---
export function MobileNav() {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-60 p-0 bg-sidebar border-sidebar-border">
        <SidebarContent onNavigate={() => setOpen(false)} />
      </SheetContent>
    </Sheet>
  );
}
