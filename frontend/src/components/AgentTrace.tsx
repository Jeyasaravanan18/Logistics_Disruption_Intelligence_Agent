"use client";
import { useState } from "react";
import type { PipelineInfo } from "@/types";
import { ChevronDown, ChevronRight, Bot, Cpu, Zap, Activity } from "lucide-react";

export default function AgentTrace({ pipeline }: { pipeline: PipelineInfo }) {
  const [open, setOpen] = useState(false);
  const traces = pipeline.traces || [];

  return (
    <div className="mb-6 border border-slate-200 bg-white rounded-lg overflow-hidden shadow-sm">
      <button 
        onClick={() => setOpen(!open)}
        className="w-full flex justify-between items-center p-4 hover:bg-slate-50 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          {open ? <ChevronDown className="w-5 h-5 text-slate-400" /> : <ChevronRight className="w-5 h-5 text-slate-400" />}
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-indigo-600" />
            <span className="font-semibold text-slate-900">
              LangGraph Workflow Telemetry Trace
            </span>
            <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded border border-indigo-200 font-medium">
              Stateful Graph
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {traces.length > 0 && (
            <span className="text-xs bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded border border-emerald-200">
              {traces.length} Nodes Traced
            </span>
          )}
          <div className="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-1 rounded-md">
            {pipeline.disruptions_collected} Signals / {pipeline.shipments_evaluated} Targets 
          </div>
        </div>
      </button>

      {open && (
        <div className="p-5 border-t border-slate-100 text-sm text-slate-600 space-y-4 bg-slate-50">
          {traces.length > 0 ? (
            <div className="space-y-3">
              {traces.map((trace, idx) => (
                <div key={idx} className="bg-white p-3 rounded-md border border-slate-200 shadow-sm">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                      <span className="font-mono font-bold text-slate-800 text-xs uppercase">
                        node: {trace.node}
                      </span>
                      {trace.used_llm && (
                        <span className="inline-flex items-center gap-1 text-[10px] bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded border border-purple-200">
                          <Cpu className="w-3 h-3" /> LLM
                        </span>
                      )}
                      {trace.fallback_used && (
                        <span className="inline-flex items-center gap-1 text-[10px] bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded border border-amber-200">
                          <Zap className="w-3 h-3" /> Fallback
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 font-mono text-xs text-slate-500">
                      <span>{trace.duration_ms}ms</span>
                      {trace.input_hash && (
                        <span className="text-[10px] text-slate-400 bg-slate-100 px-1 rounded">
                          #{trace.input_hash}
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-slate-700 text-xs pl-3.5 border-l border-indigo-200">
                    {trace.output_summary}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <div className="font-bold text-slate-900 mb-1 text-xs uppercase tracking-wider flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-indigo-500" />
                  Collector Reasoning
                </div>
                <p className="text-slate-700 bg-white p-3 rounded border border-slate-200 text-xs">
                  {pipeline.collector_reasoning}
                </p>
              </div>
              <div>
                <div className="font-bold text-slate-900 mb-1 text-xs uppercase tracking-wider flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-indigo-500" />
                  Risk Assessment Breakdown
                </div>
                <p className="text-slate-700 bg-white p-3 rounded border border-slate-200 text-xs">
                  Assessed {pipeline.shipments_evaluated} shipment corridors: {pipeline.risk_breakdown.HIGH} HIGH, {pipeline.risk_breakdown.MEDIUM} MEDIUM, {pipeline.risk_breakdown.LOW} LOW threat intersections.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
