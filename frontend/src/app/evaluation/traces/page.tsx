"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { API_BASE_URL } from "@/lib/api";
import { Loader2, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";

interface Span {
  id: string;
  name: string;
  status: string;
  latency_ms: number;
  metadata: Record<string, unknown>;
}

interface Trace {
  id: string;
  request_id: string;
  route: string;
  status: string;
  total_tokens: number;
  estimated_cost: number;
  latency_ms: number;
  created_at: string;
  spans?: Span[];
}

export default function TracesDashboard() {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [traceDetails, setTraceDetails] = useState<Trace | null>(null);

  useEffect(() => {
    fetch(API_BASE_URL + "/observability/traces?limit=100", {
      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` }
    })
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setTraces(data);
      })
      .catch(console.error)
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    if (selectedTraceId) {
      fetch(API_BASE_URL + "/observability/traces/" + selectedTraceId, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` }
      })
        .then(res => res.json())
        .then(setTraceDetails)
        .catch(console.error);
    }
  }, [selectedTraceId]);

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Left panel - Trace List */}
      <div className="w-1/3 border-r flex flex-col h-full bg-muted/20">
        <div className="p-4 border-b flex items-center">
          <Button variant="ghost" size="icon" asChild className="mr-2">
            <Link href="/evaluation">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <h2 className="font-semibold">Recent Traces</h2>
        </div>
        <div className="flex-1 overflow-auto p-4 space-y-2">
          {traces.map(trace => (
            <div 
              key={trace.id}
              onClick={() => setSelectedTraceId(trace.id)}
              className={`p-3 border rounded-lg cursor-pointer hover:bg-accent ${selectedTraceId === trace.id ? 'border-primary bg-accent' : 'bg-card'}`}
            >
              <div className="flex justify-between items-start mb-1">
                <span className="font-medium text-sm truncate">{trace.id.split('-')[0]}...</span>
                <Badge variant={trace.route === 'rag' ? 'default' : 'secondary'}>{trace.route}</Badge>
              </div>
              <div className="flex justify-between items-center text-xs text-muted-foreground">
                <span>{new Date(trace.created_at).toLocaleTimeString()}</span>
                <span>{trace.latency_ms?.toFixed(0)} ms</span>
              </div>
            </div>
          ))}
          {traces.length === 0 && <p className="text-sm text-muted-foreground p-4">No traces found.</p>}
        </div>
      </div>

      {/* Right panel - Trace Detail */}
      <div className="w-2/3 flex flex-col h-full overflow-auto p-6">
        {traceDetails ? (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold tracking-tight mb-2">Trace Details</h2>
              <div className="flex space-x-4 text-sm text-muted-foreground">
                <span>ID: {traceDetails.id}</span>
                <span>Latency: {traceDetails.latency_ms?.toFixed(0)}ms</span>
                <span>Tokens: {traceDetails.total_tokens || 0}</span>
                <span>Cost: ${traceDetails.estimated_cost?.toFixed(4) || "0.0000"}</span>
              </div>
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Span Waterfall</CardTitle>
                <CardDescription>Breakdown of operations</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {traceDetails.spans?.map(span => (
                    <div key={span.id} className="border rounded-md p-4 bg-muted/30">
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-semibold text-sm">{span.name}</span>
                        <div className="flex items-center space-x-2 text-xs">
                           <Badge variant={span.status === 'error' ? 'destructive' : 'outline'}>{span.status}</Badge>
                           <span className="font-medium">{span.latency_ms?.toFixed(0)}ms</span>
                        </div>
                      </div>
                      {span.metadata && Object.keys(span.metadata).length > 0 && (
                        <pre className="text-xs bg-muted p-2 rounded mt-2 overflow-auto max-h-40">
                          {JSON.stringify(span.metadata, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))}
                  {(!traceDetails.spans || traceDetails.spans.length === 0) && (
                    <p className="text-sm text-muted-foreground">No spans recorded for this trace.</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Select a trace from the left panel to view details
          </div>
        )}
      </div>
    </div>
  );
}
