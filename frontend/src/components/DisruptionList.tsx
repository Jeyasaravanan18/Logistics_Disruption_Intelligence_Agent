"use client";
import type { Disruption } from "@/types";
import { AlertCircle, Clock, MapPin } from "lucide-react";

interface Props {
  disruptions: Disruption[];
  collectorReasoning?: string;
}

export default function DisruptionList({ disruptions, collectorReasoning }: Props) {
  const sevCounts = disruptions.reduce<Record<string, number>>((acc, d) => {
    acc[d.severity] = (acc[d.severity] || 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Live Disruption Feed</h2>
          <p className="text-sm text-slate-500 mt-1">Real-time anomalies detected from global data sources.</p>
        </div>
      </div>

      {collectorReasoning && (
        <div className="mb-6 p-4 bg-indigo-50 border border-indigo-100 rounded-lg text-sm text-indigo-900 leading-relaxed shadow-sm">
          <span className="font-bold flex items-center gap-2 mb-1 text-indigo-700">
            <AlertCircle className="w-4 h-4" /> AI Collector Note
          </span>
          {collectorReasoning}
        </div>
      )}

      {disruptions.length === 0 && (
        <div className="p-8 saas-panel text-center flex flex-col items-center justify-center">
          <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center mb-3">
            <AlertCircle className="w-6 h-6 text-emerald-500" />
          </div>
          <h3 className="text-base font-semibold text-slate-900">No Anomalies Detected</h3>
          <p className="text-sm text-slate-500 mt-1">Global logistics networks are operating normally.</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-5">
        {disruptions.map((d) => {
          const isHigh = d.severity === 'HIGH';
          const isMed = d.severity === 'MEDIUM';
          
          return (
            <div key={d.id} className="saas-panel p-5 flex flex-col justify-between group hover:border-slate-300 transition-colors">
              <div>
                <div className="flex justify-between items-start mb-3">
                  <div className="font-semibold text-slate-900 flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${isHigh ? 'bg-red-500' : isMed ? 'bg-amber-500' : 'bg-emerald-500'}`}></span>
                    {d.subtype}
                  </div>
                  <div className={`px-2.5 py-0.5 text-[10px] font-bold border rounded-md uppercase tracking-wider ${
                    isHigh ? 'bg-red-50 text-red-700 border-red-200' : 
                    isMed ? 'bg-amber-50 text-amber-700 border-amber-200' : 
                    'bg-emerald-50 text-emerald-700 border-emerald-200'
                  }`}>
                    {d.severity}
                  </div>
                </div>
                <p className="text-sm text-slate-600 leading-relaxed mb-6">{d.description}</p>
              </div>
              
              <div className="flex justify-between items-center pt-4 mt-auto border-t border-slate-100">
                <div className="text-xs font-medium text-slate-500 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5" />
                  {d.location}
                </div>
                <div className="text-xs font-medium text-slate-500 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  {new Date(d.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
