"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Shield, Loader2, UserCog, Check, X } from "lucide-react";
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
import { useToast } from "@/components/ui/use-toast";
import { UserProfile } from "@/lib/types";

// Roles available for assignment
const AVAILABLE_ROLES = ["USER", "employee", "hr", "finance", "marketing", "manager", "c_level", "admin"];

function UserRow({ user }: { user: UserProfile }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [isEditingRoles, setIsEditingRoles] = useState(false);
  const [selectedRoles, setSelectedRoles] = useState<string[]>(user.roles.map(r => r.name));

  const statusMutation = useMutation({
    mutationFn: (active: boolean) => api.users.updateStatus(user.id, active),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast({ title: "Status updated" });
    },
    onError: (err: Error) => {
      toast({ title: "Update failed", description: err.message, variant: "destructive" });
    }
  });

  const rolesMutation = useMutation({
    mutationFn: (roles: string[]) => api.users.updateRoles(user.id, roles),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setIsEditingRoles(false);
      toast({ title: "Roles updated" });
    },
    onError: (err: Error) => {
      toast({ title: "Update failed", description: err.message, variant: "destructive" });
    }
  });

  const handleSaveRoles = () => {
    rolesMutation.mutate(selectedRoles);
  };

  const toggleRole = (role: string) => {
    setSelectedRoles(prev => 
      prev.includes(role) ? prev.filter(r => r !== role) : [...prev, role]
    );
  };

  return (
    <TableRow>
      <TableCell className="font-medium">
        <div>{user.full_name}</div>
        <div className="text-xs text-muted-foreground">{user.email}</div>
      </TableCell>
      <TableCell>
        {isEditingRoles ? (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap gap-1">
              {AVAILABLE_ROLES.map(role => (
                <Badge 
                  key={role} 
                  variant={selectedRoles.includes(role) ? "default" : "outline"}
                  className="cursor-pointer"
                  onClick={() => toggleRole(role)}
                >
                  {role}
                </Badge>
              ))}
            </div>
            <div className="flex gap-2 mt-1">
              <Button size="sm" onClick={handleSaveRoles} disabled={rolesMutation.isPending}>
                {rolesMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Check className="h-3 w-3 mr-1" />} Save
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { setIsEditingRoles(false); setSelectedRoles(user.roles.map(r => r.name)); }}>
                <X className="h-3 w-3 mr-1" /> Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <div className="flex flex-wrap gap-1">
              {user.roles.map(r => (
                <Badge key={r.name} variant="secondary">{r.name}</Badge>
              ))}
            </div>
            <Button variant="ghost" size="icon" onClick={() => setIsEditingRoles(true)} className="h-6 w-6">
              <UserCog className="h-3 w-3" />
            </Button>
          </div>
        )}
      </TableCell>
      <TableCell>
        <Badge variant={user.is_active ? "default" : "destructive"}>
          {user.is_active ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell className="text-right">
        <Button 
          variant={user.is_active ? "destructive" : "default"} 
          size="sm"
          onClick={() => statusMutation.mutate(!user.is_active)}
          disabled={statusMutation.isPending}
        >
          {statusMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : (user.is_active ? "Deactivate" : "Activate")}
        </Button>
      </TableCell>
    </TableRow>
  );
}

export default function UsersPage() {
  const { hasPermission } = useAuth();
  
  const { data: users, isLoading, error } = useQuery({
    queryKey: ["users"],
    queryFn: api.users.list,
  });

  if (!hasPermission("users.manage") && !hasPermission("users.read")) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <Shield className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-lg font-semibold">Access Denied</h2>
          <p className="text-muted-foreground">You don&apos;t have permission to view users.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex-1 overflow-y-auto px-4 py-8">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 animate-fade-in">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight mb-1 text-foreground">User Management</h1>
            <p className="text-sm text-muted-foreground">
              Manage users, roles, and access across the enterprise platform.
            </p>
          </div>

          <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
            {isLoading ? (
              <div className="flex h-40 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : error ? (
              <div className="p-8 text-center text-muted-foreground">Failed to load users</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Roles</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users?.map(user => (
                    <UserRow key={user.id} user={user} />
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
