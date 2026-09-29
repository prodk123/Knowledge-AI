import { useState } from "react";
import { ShieldAlert, ShieldCheck, Shield, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/api";

export interface ApprovalData {
  id: string;
  tool_name: string;
  risk_level: "low" | "medium" | "high" | "critical";
  requested_action_desc: string;
  status: "pending" | "approved" | "rejected" | "expired" | "failed";
  expires_at?: string;
  [key: string]: unknown;
}

export function ApprovalCard({ approval }: { approval: ApprovalData }) {
  const [status, setStatus] = useState(approval.status);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isPending = status === "pending";
  const isApproved = status === "approved";
  const isRejected = status === "rejected";
  const isExpired = status === "expired";
  const isResuming = isSubmitting && status === "pending";

  const handleAction = async (action: "approve" | "reject") => {
    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/approvals/${approval.id}/${action}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      });

      if (!response.ok) throw new Error(`Failed to ${action}`);
      setStatus(action === "approve" ? "approved" : "rejected");
    } catch (err) {
      console.error(err);
      setStatus("failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const getRiskColor = (level: string) => {
    switch (level.toLowerCase()) {
      case "critical": return "text-destructive bg-destructive/10 border-destructive/20";
      case "high": return "text-orange-600 bg-orange-500/10 border-orange-500/20 dark:text-orange-400";
      case "medium": return "text-yellow-600 bg-yellow-500/10 border-yellow-500/20 dark:text-yellow-400";
      default: return "text-blue-600 bg-blue-500/10 border-blue-500/20 dark:text-blue-400";
    }
  };

  const getRiskIcon = (level: string) => {
    switch (level.toLowerCase()) {
      case "critical":
      case "high": return <ShieldAlert className="h-3.5 w-3.5" />;
      default: return <Shield className="h-3.5 w-3.5" />;
    }
  };

  return (
    <div className={cn(
      "my-4 overflow-hidden rounded-xl border max-w-md animate-fade-in transition-colors",
      isPending ? "border-[var(--border)] bg-[var(--card)]" : 
      isApproved ? "border-green-500/30 bg-green-50/50 dark:bg-green-950/20" : 
      isRejected ? "border-muted bg-muted/30" : 
      "border-destructive/30 bg-destructive/5"
    )}>
      <div className="flex flex-col gap-3 p-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={cn(
              "flex h-6 w-6 items-center justify-center rounded-md border",
              isPending ? "bg-primary/10 text-primary border-primary/20" :
              isApproved ? "bg-green-500/10 text-green-600 border-green-500/20 dark:text-green-400" :
              isRejected ? "bg-muted text-muted-foreground border-border" :
              "bg-destructive/10 text-destructive border-destructive/20"
            )}>
              {isApproved ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldAlert className="h-3.5 w-3.5" />}
            </div>
            <span className="text-sm font-semibold text-foreground">
              {isResuming ? "Processing..." :
               isPending ? "Approval Required" : 
               isApproved ? "Approved — Workflow Resuming" : 
               isRejected ? "Rejected" : 
               isExpired ? "Expired" : "Action Failed"}
            </span>
          </div>
          
          <div className={cn("flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide", getRiskColor(approval.risk_level))}>
            {getRiskIcon(approval.risk_level)}
            {approval.risk_level} Risk
          </div>
        </div>

        {/* Content */}
        <div className="rounded-lg bg-background/50 p-3 border border-[var(--border-subtle)]">
          <div className="mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            {approval.tool_name.replace(/_/g, " ")}
          </div>
          <p className="text-sm text-foreground leading-relaxed">
            {approval.requested_action_desc}
          </p>
        </div>

        {/* Expiration warning */}
        {isPending && approval.expires_at && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5" />
            <span>Expires: {new Date(approval.expires_at).toLocaleString()}</span>
          </div>
        )}
      </div>

      {/* Actions Footer */}
      {isPending && (
        <div className="flex gap-2 border-t border-border/50 bg-muted/20 p-3">
          <Button
            variant="outline"
            className="flex-1 bg-background hover:bg-muted text-muted-foreground h-10 font-medium transition-colors"
            disabled={isSubmitting}
            onClick={() => handleAction("reject")}
          >
            Reject
          </Button>
          <Button
            className="flex-1 bg-primary text-primary-foreground hover:bg-primary/90 h-10 font-medium transition-colors shadow-sm"
            disabled={isSubmitting}
            onClick={() => handleAction("approve")}
          >
            Approve
          </Button>
        </div>
      )}
    </div>
  );
}
