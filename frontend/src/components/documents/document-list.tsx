"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { format } from "date-fns";
import { FileText, Loader2, RefreshCw, MoreVertical, Trash2, Shield, Check, X } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ui/use-toast";
import { DocumentStatusResponse } from "@/lib/types";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const AVAILABLE_ROLES = ["USER", "employee", "hr", "finance", "marketing", "manager", "c_level", "admin"];

function DocumentRow({ doc }: { doc: DocumentStatusResponse }) {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [isEditingRoles, setIsEditingRoles] = useState(false);
  const [selectedRoles, setSelectedRoles] = useState<string[]>(doc.allowed_roles || AVAILABLE_ROLES);

  const deleteMutation = useMutation({
    mutationFn: () => api.documents.delete(doc.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast({ title: "Document deleted" });
    },
    onError: (err: Error) => {
      toast({ title: "Delete failed", description: err.message, variant: "destructive" });
    }
  });

  const rolesMutation = useMutation({
    mutationFn: (roles: string[]) => api.documents.updateRoles(doc.id, roles),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      setIsEditingRoles(false);
      toast({ title: "Access updated" });
    },
    onError: (err: Error) => {
      toast({ title: "Update failed", description: err.message, variant: "destructive" });
    }
  });

  const canManage = hasPermission("documents.manage");
  const canDelete = hasPermission("documents.delete") || canManage;

  const toggleRole = (role: string) => {
    setSelectedRoles(prev => 
      prev.includes(role) ? prev.filter(r => r !== role) : [...prev, role]
    );
  };

  return (
    <TableRow>
      <TableCell className="font-medium">
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            {doc.original_filename}
          </div>
          {isEditingRoles ? (
            <div className="mt-2 pl-6 space-y-2">
              <div className="flex flex-wrap gap-1">
                {AVAILABLE_ROLES.map(role => (
                  <Badge 
                    key={role} 
                    variant={selectedRoles.includes(role) ? "default" : "outline"}
                    className="cursor-pointer text-[10px] py-0 px-1.5"
                    onClick={() => toggleRole(role)}
                  >
                    {role}
                  </Badge>
                ))}
              </div>
              <div className="flex gap-2">
                <Button size="sm" className="h-6 text-xs px-2" onClick={() => rolesMutation.mutate(selectedRoles)} disabled={rolesMutation.isPending}>
                  {rolesMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Check className="h-3 w-3 mr-1" />} Save
                </Button>
                <Button size="sm" variant="ghost" className="h-6 text-xs px-2" onClick={() => { setIsEditingRoles(false); setSelectedRoles(doc.allowed_roles || AVAILABLE_ROLES); }}>
                  <X className="h-3 w-3 mr-1" /> Cancel
                </Button>
              </div>
            </div>
          ) : (
            doc.allowed_roles && doc.allowed_roles.length > 0 && (
              <div className="flex flex-wrap gap-1 pl-6 mt-1">
                {doc.allowed_roles.map(r => (
                  <Badge key={r} variant="secondary" className="text-[9px] px-1 py-0">{r}</Badge>
                ))}
              </div>
            )
          )}
        </div>
      </TableCell>
      <TableCell className="text-muted-foreground uppercase text-xs font-semibold">
        {doc.file_type.replace(".", "")}
      </TableCell>
      <TableCell className="text-muted-foreground text-sm">
        {(doc.file_size / 1024).toFixed(1)} KB
      </TableCell>
      <TableCell>
        <Badge
          variant={
            doc.status === "processed"
              ? "default"
              : doc.status === "failed"
              ? "destructive"
              : "secondary"
          }
        >
          {doc.status}
        </Badge>
      </TableCell>
      <TableCell className="text-muted-foreground text-sm">
        {format(new Date(doc.created_at), "MMM d, yyyy")}
      </TableCell>
      <TableCell className="text-right">
        {(canManage || canDelete) && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Actions</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {canManage && (
                <DropdownMenuItem onClick={() => setIsEditingRoles(true)}>
                  <Shield className="mr-2 h-4 w-4" />
                  <span>Manage Access</span>
                </DropdownMenuItem>
              )}
              {canDelete && (
                <DropdownMenuItem 
                  className="text-destructive focus:text-destructive"
                  onClick={() => {
                    if (confirm("Are you sure you want to delete this document?")) {
                      deleteMutation.mutate();
                    }
                  }}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  <span>Delete</span>
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </TableCell>
    </TableRow>
  );
}

export function DocumentList() {
  const { data: documents, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: ["documents"],
    queryFn: api.documents.list,
    refetchInterval: 5000,
  });

  if (isLoading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-40 gap-4 text-center">
        <p className="text-muted-foreground text-sm">Failed to load documents.</p>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" /> Try again
        </Button>
      </div>
    );
  }

  if (!documents || documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center border rounded-xl border-dashed">
        <div className="rounded-full bg-muted p-4 mb-4">
          <FileText className="h-6 w-6 text-muted-foreground" />
        </div>
        <h3 className="font-medium tracking-tight mb-1">No documents yet</h3>
        <p className="text-sm text-muted-foreground mb-4 max-w-sm">
          Upload your first document to build your knowledge base.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
      <div className="flex items-center justify-between p-4 border-b">
        <div className="font-semibold">{documents.length} Documents</div>
        <Button variant="ghost" size="icon" onClick={() => refetch()} disabled={isRefetching}>
          <RefreshCw className={`h-4 w-4 ${isRefetching ? 'animate-spin' : ''}`} />
        </Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Document</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Date</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((doc) => (
            <DocumentRow key={doc.id} doc={doc} />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
