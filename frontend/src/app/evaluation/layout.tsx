"use client";

import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loader2 } from "lucide-react";

export default function EvaluationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { hasPermission, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !hasPermission("evaluation.view")) {
      router.push("/");
    }
  }, [hasPermission, isLoading, router]);

  if (isLoading || !hasPermission("evaluation.view")) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col">
      {children}
    </div>
  );
}
