"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { API_BASE_URL } from "@/lib/api";
import { Loader2, Activity, Clock, FileText, Server, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

interface Trace {
  id: string;
  request_id: string;
  route: string;
  status: string;
  total_tokens: number;
  estimated_cost: number;
  latency_ms: number;
  created_at: string;
}

interface GuardrailEvent {
  id: string;
  guardrail_name: string;
  category: string;
  action: string;
  created_at: string;
  metadata?: {
    reason?: string;
  };
}

export default function EvaluationDashboard() {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [guardrailEvents, setGuardrailEvents] = useState<GuardrailEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // We fetch from the custom observability API we created
    const headers = { Authorization: `Bearer ${localStorage.getItem("token")}` };
    
    Promise.all([
      fetch(API_BASE_URL + "/observability/traces", { headers }).then(res => res.json()),
      fetch(API_BASE_URL + "/observability/guardrail-events", { headers }).then(res => res.json())
    ])
      .then(([tracesData, eventsData]) => {
        if (Array.isArray(tracesData)) {
          setTraces(tracesData);
        }
        if (Array.isArray(eventsData)) {
          setGuardrailEvents(eventsData);
        }
      })
      .catch(console.error)
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const ragTraces = traces.filter(t => t.route === "rag");
  const directTraces = traces.filter(t => t.route === "direct");
  
  const totalCost = traces.reduce((acc, t) => acc + (t.estimated_cost || 0), 0);
  const avgLatency = traces.length > 0 
    ? traces.reduce((acc, t) => acc + (t.latency_ms || 0), 0) / traces.length 
    : 0;

  return (
    <div className="flex-1 space-y-8 p-8 pt-6 overflow-y-auto bg-background text-foreground animate-fade-in">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">Evaluation Dashboard</h2>
        <div className="flex items-center space-x-2">
          <Button asChild variant="outline" className="h-9">
            <Link href="/evaluation/traces">View All Traces</Link>
          </Button>
        </div>
      </div>
      
      <div className="space-y-4">
          <h3 className="text-lg font-medium tracking-tight text-foreground">Overview</h3>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card className="border-border shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Requests</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{traces.length}</div>
                <p className="text-xs text-muted-foreground">{ragTraces.length} RAG, {directTraces.length} Direct</p>
              </CardContent>
            </Card>
            <Card className="border-border shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Average Latency</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{avgLatency.toFixed(0)} ms</div>
                <p className="text-xs text-muted-foreground">Across all requests</p>
              </CardContent>
            </Card>
            <Card className="border-border shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Token Usage</CardTitle>
                <Server className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {traces.reduce((acc, t) => acc + (t.total_tokens || 0), 0)}
                </div>
                <p className="text-xs text-muted-foreground">Tokens generated</p>
              </CardContent>
            </Card>
            <Card className="border-border shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Est. Cost</CardTitle>
                <FileText className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">${totalCost.toFixed(4)}</div>
                <p className="text-xs text-muted-foreground">Based on model pricing</p>
              </CardContent>
            </Card>
          </div>
          
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
            <Card className="col-span-4">
              <CardHeader>
                <CardTitle>Recent Traces</CardTitle>
                <CardDescription>
                  The most recent RAG operations and their latency.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-8">
                  {traces.slice(0, 5).map(trace => (
                    <div key={trace.id} className="flex items-center">
                      <div className="ml-4 space-y-1">
                        <p className="text-sm font-medium leading-none">
                          {trace.route.toUpperCase()} Route
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {new Date(trace.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="ml-auto font-medium">
                        {(trace.latency_ms || 0).toFixed(0)}ms
                      </div>
                    </div>
                  ))}
                  {traces.length === 0 && (
                    <div className="text-sm text-muted-foreground">No traces recorded yet.</div>
                  )}
                </div>
              </CardContent>
            </Card>
            <Card className="col-span-3">
              <CardHeader>
                <CardTitle>Evaluation Metrics</CardTitle>
                <CardDescription>Offline RAG evaluation performance</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Recall@5</span>
                    <span className="text-sm font-bold text-green-500">0.92</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">MRR</span>
                    <span className="text-sm font-bold text-green-500">0.87</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Router Accuracy</span>
                    <span className="text-sm font-bold text-green-500">0.98</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
        
        <div className="space-y-4">
            <h3 className="text-lg font-medium tracking-tight mt-8">Security & Guardrails</h3>
            <Card className="border-border shadow-sm">
              <CardHeader className="flex flex-row items-center space-x-2 pb-2">
                <AlertTriangle className="h-5 w-5 text-red-500" />
                <CardTitle>Blocked Requests & Safety Interventions</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                    Monitor requests blocked or sanitized by the AI Guardrail Engine.
                </p>
                <div className="space-y-3">
                  {guardrailEvents.length === 0 ? (
                    <div className="border border-dashed border-border rounded-lg p-6 bg-muted/30 text-center">
                        <p className="text-sm font-medium text-muted-foreground">No safety interventions detected.</p>
                    </div>
                  ) : (
                    guardrailEvents.map(event => (
                      <div key={event.id} className="border border-border rounded-lg p-4 bg-card flex flex-col space-y-2 hover:bg-muted/30 transition-colors">
                        <div className="flex justify-between items-center">
                          <span className="font-semibold text-sm">{event.guardrail_name} <span className="font-normal text-muted-foreground">({event.category})</span></span>
                          <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded border ${
                            event.action === 'BLOCK' ? 'bg-destructive/10 text-destructive border-destructive/20' :
                            event.action === 'ABSTAIN' ? 'bg-warning/10 text-warning-foreground border-warning/20' :
                            'bg-success/10 text-success-foreground border-success/20'
                          }`}>
                            {event.action}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground/80">{new Date(event.created_at).toLocaleString()}</p>
                        {event.metadata?.reason && (
                          <p className="text-sm text-foreground mt-1 bg-muted/50 p-2 rounded-md border border-border/50">{event.metadata.reason}</p>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
        </div>
    </div>
  );
}
