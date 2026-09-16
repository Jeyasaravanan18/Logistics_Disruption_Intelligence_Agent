"use client";
import { useState } from "react";
import type { PipelineInfo } from "@/types";
import { ChevronDown, ChevronRight, Terminal, Bot } from "lucide-react";

export default function AgentTrace({ pipeline }: { pipeline: PipelineInfo }) {
  const [open, setOpen] = useState(false);

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
              AI Decision Trace
            </span>
          </div>
        </div>
        <div className="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-1 rounded-md">
          {pipeline.disruptions_collected} Signals / {pipeline.shipments_evaluated} Targets 
        </div>
      </button>

      {open && (
        <div className="p-5 border-t border-slate-100 text-sm text-slate-600 space-y-6 bg-slate-50">
          
          <div>
            <div className="font-bold text-slate-900 mb-2 uppercase tracking-widest text-xs flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full"></span>
              DataCollectorAgent
            </div>
            <p className="pl-4 border-l-2 border-indigo-200 text-slate-700 leading-relaxed bg-white p-3 rounded-r-md border border-l-0 border-slate-200 shadow-sm">
              {pipeline.collector_reasoning}
            </p>
          </div>

          <div>
            <div className="font-bold text-slate-900 mb-2 uppercase tracking-widest text-xs flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full"></span>
              RiskEvaluatorAgent
            </div>
            <p className="pl-4 border-l-2 border-indigo-200 text-slate-700 leading-relaxed bg-white p-3 rounded-r-md border border-l-0 border-slate-200 shadow-sm">
              Cross-referenced {pipeline.disruptions_collected} active anomalies against {pipeline.shipments_evaluated} active supply line trajectories. 
              Identified {pipeline.risk_breakdown.HIGH} HIGH, {pipeline.risk_breakdown.MEDIUM} MEDIUM, and {pipeline.risk_breakdown.LOW} LOW threat intersections.
            </p>
          </div>

          <div>
            <div className="font-bold text-slate-900 mb-2 uppercase tracking-widest text-xs flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full"></span>
              RecommendationAgent
            </div>
            <p className="pl-4 border-l-2 border-indigo-200 text-slate-700 leading-relaxed bg-white p-3 rounded-r-md border border-l-0 border-slate-200 shadow-sm">
              Synthesized evasion strategies and delay calculations across all non-nominal routes. Re-routing vectors compiled.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
