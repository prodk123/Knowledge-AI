import { useState } from "react";
import { ChevronDown, ChevronRight, Activity, CheckCircle2, CircleDashed } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ToolActivityData {
  tool_name: string;
  status: "running" | "completed" | "failed";
  details?: string;
}

export interface AgentActivityData {
  agent_name: string;
  status: "running" | "completed" | "failed";
  tasks: ToolActivityData[];
}

// ─── Map technical tool names to human-readable UI ────────
function getToolLabel(toolName: string, status: string) {
  const name = toolName.toLowerCase();
  
  if (name.includes("web_search")) return status === "running" ? "Searching the web" : "Searched the web";
  if (name.includes("enterprise_search")) return status === "running" ? "Searching enterprise knowledge" : "Searched enterprise knowledge";
  if (name.includes("calculator")) return status === "running" ? "Calculating" : "Calculated result";
  if (name.includes("calendar_search")) return status === "running" ? "Checking calendar" : "Checked calendar";
  if (name.includes("calendar_create")) return status === "running" ? "Preparing calendar event" : "Prepared calendar event";
  if (name.includes("send_email")) return status === "running" ? "Preparing email" : "Prepared email";
  
  // Fallback formatter
  const formatted = toolName.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  return status === "running" ? `Running ${formatted}` : `Completed ${formatted}`;
}

export function AgentActivity({ activities }: { activities: AgentActivityData[] }) {
  const [expanded, setExpanded] = useState(false);

  if (!activities || activities.length === 0) return null;

  const isAllComplete = activities.every(a => a.status === "completed");
  const isAnyRunning = activities.some(a => a.status === "running");

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-border/40 bg-muted/20 max-w-md transition-all animate-fade-in">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-3.5 py-2.5 hover:bg-muted/40 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={cn(
            "flex h-7 w-7 items-center justify-center rounded-lg border",
            isAllComplete ? "bg-green-500/10 text-green-600 border-green-500/20 dark:text-green-400" :
            isAnyRunning ? "bg-primary/10 text-primary border-primary/20" :
            "bg-muted text-muted-foreground border-[var(--border)]"
          )}>
            {isAllComplete ? <CheckCircle2 className="h-4 w-4" /> : <Activity className="h-4 w-4 animate-pulse" />}
          </div>
          <div className="flex flex-col items-start">
            <span className="text-sm font-medium text-foreground/80">
              {isAnyRunning ? "Agent workflow running" : "Agent workflow complete"}
            </span>
            <span className="text-xs text-muted-foreground">
              {activities.length} agent{activities.length !== 1 ? 's' : ''} involved
            </span>
          </div>
        </div>
        <div className="text-muted-foreground shrink-0">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border/40 bg-muted/10 px-3.5 py-3">
          <div className="space-y-4">
            {activities.map((agent, i) => (
              <div key={i} className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="h-px flex-1 bg-border/40" />
                  <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70">
                    {agent.agent_name.replace(/_/g, " ")}
                  </span>
                  <div className="h-px flex-1 bg-border/40" />
                </div>
                
                <div className="space-y-1.5 px-1">
                  {agent.tasks.map((task, j) => {
                    const isTaskRunning = task.status === "running";
                    const isTaskComplete = task.status === "completed";
                    
                    return (
                      <div key={j} className="flex items-start gap-3 py-1">
                        <div className="mt-0.5 shrink-0">
                          {isTaskComplete ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                          ) : isTaskRunning ? (
                            <CircleDashed className="h-3.5 w-3.5 text-primary animate-[spin_3s_linear_infinite]" />
                          ) : (
                            <CircleDashed className="h-3.5 w-3.5 text-muted-foreground" />
                          )}
                        </div>
                        <div className="flex flex-col">
                          <span className={cn(
                            "text-[0.8125rem] font-medium",
                            isTaskRunning ? "text-foreground/90" : "text-muted-foreground/80"
                          )}>
                            {getToolLabel(task.tool_name, task.status)}
                          </span>
                          {task.details && (
                            <span className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                              {task.details}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
