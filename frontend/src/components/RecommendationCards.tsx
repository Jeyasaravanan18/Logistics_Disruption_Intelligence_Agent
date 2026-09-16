"use client";
import { useState } from "react";
import type { Recommendation, PipelineInfo } from "@/types";
import AgentTrace from "@/components/AgentTrace";
import { AlertCircle, ArrowRight, Clock, Map, CheckCircle2 } from "lucide-react";

interface Props {
  recommendations: Recommendation[];
  pipeline?: PipelineInfo;
  onRunAnalysis?: () => void;
  loading?: boolean;
  onSimulateRoute?: (shipmentId: string) => void;
}

export default function RecommendationCards({
  recommendations,
  pipeline,
  onRunAnalysis,
  loading,
  onSimulateRoute,
}: Props) {
  const [filter, setFilter] = useState("All");

  const filters = ["All", "HIGH", "MEDIUM", "LOW", "SAFE"];
  const shown = recommendations.filter((r) => filter === "All" || r.risk_level === filter);

  if (recommendations.length === 0) {
    return (
      <div>
        <div className="mb-6">
          <h2 className="text-lg font-bold text-slate-900">AI Strategy Directives</h2>
          <p className="text-sm text-slate-500 mt-1">
            Automated routing decisions and disruption mitigation strategies.
          </p>
        </div>
        <div className="flex flex-col items-center justify-center p-12 text-center saas-panel bg-white border border-slate-200 rounded-xl min-h-[300px]">
          <AlertCircle className="w-12 h-12 text-indigo-500 mb-4" />
          <h3 className="text-lg font-bold text-slate-900 mb-1">No AI Strategy Directives Generated Yet</h3>
          <p className="text-sm text-slate-500 max-w-md mb-6">
            Run the AI recommendation agent to analyze active route disruptions and produce automated rerouting and customer messaging directives.
          </p>
          {onRunAnalysis && (
            <button
              onClick={onRunAnalysis}
              disabled={loading}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg shadow-sm transition-all"
            >
              {loading ? "Generating Strategy..." : "Run AI Strategy Generation"}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">AI Strategy Directives</h2>
        <p className="text-sm text-slate-500 mt-1">
          Automated routing decisions and disruption mitigation strategies.
        </p>
      </div>

      {pipeline && <AgentTrace pipeline={pipeline} />}

      <div className="flex gap-2 mb-6">
        {filters.map((f) => {
          const active = filter === f;
          return (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
                active 
                  ? 'bg-blue-600 text-white shadow-sm' 
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}>
              {f}
            </button>
          )
        })}
      </div>

      <div className="space-y-4">
        {shown.map((rec) => {
          const isSafe = rec.risk_level === "SAFE";
          return (
            <div key={rec.shipment_id} className={`saas-panel overflow-hidden ${!isSafe ? 'border-l-4 border-l-red-500' : 'border-l-4 border-l-emerald-500'}`}>
              
              <div className="p-6">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <div className="font-bold text-lg text-slate-900 mb-1 flex items-center gap-3">
                      {rec.shipment_id}
                      <span className="text-slate-500 font-medium text-sm">{rec.origin} &rarr; {rec.destination}</span>
                    </div>
                    <div className="text-xs text-slate-500 font-medium flex items-center gap-3">
                      <span>{rec.route_highway}</span>
                      <span className="w-1 h-1 bg-slate-300 rounded-full"></span>
                      <span>{rec.cargo_type}</span>
                      <span className="w-1 h-1 bg-slate-300 rounded-full"></span>
                      <span className="text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md">Priority: {rec.delivery_priority}</span>
                    </div>
                  </div>
                  <div className={`px-3 py-1 text-xs font-bold border rounded-full uppercase tracking-wider flex items-center gap-1.5 ${
                    rec.risk_level === 'HIGH' ? 'bg-red-50 text-red-700 border-red-200' : 
                    rec.risk_level === 'MEDIUM' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                    rec.risk_level === 'SAFE' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 
                    'bg-slate-100 text-slate-700 border-slate-200'
                  }`}>
                    {rec.risk_level} Risk
                  </div>
                </div>

                {!isSafe ? (
                  <div className="grid grid-cols-2 gap-8 pt-6 border-t border-slate-100">
                    <div className="space-y-6">
                      <div>
                        <div className="flex items-center gap-2 mb-2 text-slate-900">
                          <AlertCircle className="w-4 h-4 text-red-500" />
                          <div className="text-sm font-bold">Threat Analysis</div>
                        </div>
                        <p className="text-sm text-slate-600 leading-relaxed border-l-2 border-slate-200 pl-3">
                          {rec.reason}
                          {rec.distance_to_disruption_km && ` Proximity: ${rec.distance_to_disruption_km.toFixed(0)} km.`}
                        </p>
                      </div>

                      <div>
                        <div className="flex items-center gap-2 mb-2 text-slate-900">
                          <ArrowRight className="w-4 h-4 text-blue-500" />
                          <div className="text-sm font-bold">Action Directive</div>
                        </div>
                        <p className="text-sm text-blue-900 leading-relaxed border-l-2 border-blue-500 pl-3 bg-blue-50/50 py-2 pr-2 rounded-r-md">
                          {rec.suggested_action}
                        </p>
                      </div>
                    </div>

                    <div className="space-y-6">
                      {rec.alternate_route && (
                        <div>
                          <div className="flex items-center gap-2 mb-2 text-slate-900">
                            <Map className="w-4 h-4 text-indigo-500" />
                            <div className="text-sm font-bold">Route Override</div>
                          </div>
                          <p className="text-sm text-indigo-900 bg-indigo-50 border border-indigo-100 p-3 rounded-md font-medium">
                            {rec.alternate_route}
                          </p>
                        </div>
                      )}

                      <div className="grid grid-cols-2 gap-4">
                        {rec.estimated_delay_hours != null && (
                          <div className="bg-slate-50 border border-slate-100 p-3 rounded-lg">
                            <div className="flex items-center gap-2 mb-1 text-slate-500">
                              <Clock className="w-3.5 h-3.5" />
                              <div className="text-[10px] font-bold uppercase tracking-wider">Delay Est.</div>
                            </div>
                            <div className="text-2xl font-bold text-amber-600">
                              +{rec.estimated_delay_hours}h
                            </div>
                          </div>
                        )}
                        {rec.disruption_type && (
                          <div className="bg-slate-50 border border-slate-100 p-3 rounded-lg">
                            <div className="flex items-center gap-2 mb-1 text-slate-500">
                              <AlertCircle className="w-3.5 h-3.5" />
                              <div className="text-[10px] font-bold uppercase tracking-wider">Type</div>
                            </div>
                            <div className="text-sm font-semibold text-slate-700 mt-1">
                              {rec.disruption_type}
                            </div>
                          </div>
                        )}
                      </div>

                      {onSimulateRoute && (
                        <button
                          onClick={() => onSimulateRoute(rec.shipment_id)}
                          className="w-full py-2 px-3 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-2 shadow-sm transition-all hover:shadow"
                        >
                          <Map className="w-3.5 h-3.5" />
                          <span>Simulate Alternate Route on Map</span>
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-100 p-4 rounded-lg flex items-center gap-3 font-medium pt-4 border-t-0 mt-4">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    Target trajectory is nominal. No action required.
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
