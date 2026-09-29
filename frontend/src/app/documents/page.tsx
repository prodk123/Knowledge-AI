"use client"

import { DocumentList } from "@/components/documents/document-list";
import { UploadZone } from "@/components/documents/upload-zone";
import { useAuth } from "@/lib/auth-context";

export default function DocumentsPage() {
  const { hasPermission } = useAuth();
  
  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex-1 overflow-y-auto px-4 py-8">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 animate-fade-in">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight mb-1 text-foreground">Knowledge Base</h1>
            <p className="text-sm text-muted-foreground">
              Manage the enterprise documents that power your AI assistant.
            </p>
          </div>
          {hasPermission("documents.upload") && <UploadZone />}
          <DocumentList />
        </div>
      </div>
    </div>
  );
}
