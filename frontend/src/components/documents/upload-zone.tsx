"use client";

import { useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { UploadCloud, Loader2 } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

export function UploadZone() {
  const [isDragging, setIsDragging] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const uploadMutation = useMutation({
    mutationFn: api.documents.upload,
    onSuccess: (data) => {
      toast({
        title: "Upload started",
        description: `${data.filename} is now being processed.`,
      });
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error) => {
      toast({
        title: "Upload failed",
        description: error instanceof Error ? error.message : "An error occurred",
        variant: "destructive",
      });
    },
  });

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        uploadMutation.mutate(files[0]);
      }
    },
    [uploadMutation]
  );

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      uploadMutation.mutate(e.target.files[0]);
    }
  };

  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={`relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-colors ${
        isDragging
          ? "border-primary bg-primary/5"
          : "border-border hover:bg-muted/50"
      }`}
    >
      <input
        type="file"
        className="absolute inset-0 cursor-pointer opacity-0"
        onChange={onChange}
        disabled={uploadMutation.isPending}
        accept=".txt,.md,.pdf,.docx"
      />
      
      {uploadMutation.isPending ? (
        <div className="flex flex-col items-center justify-center text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <h3 className="text-lg font-semibold tracking-tight">Uploading...</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Please wait while we transfer the file.
          </p>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center text-center">
          <div className="rounded-full bg-primary/10 p-4 mb-4">
            <UploadCloud className="h-8 w-8 text-primary" />
          </div>
          <h3 className="text-lg font-semibold tracking-tight">
            Drop documents here or click to browse
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            Supported formats: PDF, DOCX, TXT, MD
          </p>
        </div>
      )}
    </div>
  );
}
