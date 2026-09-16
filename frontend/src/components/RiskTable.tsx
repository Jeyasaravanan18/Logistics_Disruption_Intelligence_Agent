"use client";
import type { Recommendation } from "@/types";
import { Shield, ShieldAlert, ShieldCheck, AlertTriangle } from "lucide-react";

interface Props {
  recommendations: Recommendation[];
  riskBreakdown: { HIGH: number; MEDIUM: number; LOW: number; SAFE: number };
  onRunAnalysis?: () => void;
  loading?: boolean;
}

export default function RiskTable({ recommendations, riskBreakdown, onRunAnalysis, loading }: Props) {
  const total = Object.values(riskBreakdown).reduce((a, b) => a + b, 0);

  if (recommendations.length === 0) {
    return (
      <div>
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Risk Matrix</h2>
            <p className="text-sm text-slate-500 mt-1">Live threat assessment across active fleet.</p>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center p-12 text-center saas-panel bg-white border border-slate-200 rounded-xl min-h-[300px]">
          <ShieldAlert className="w-12 h-12 text-blue-500 mb-4" />
          <h3 className="text-lg font-bold text-slate-900 mb-1">No Risk Matrix Data Yet</h3>
          <p className="text-sm text-slate-500 max-w-md mb-6">
            The 4-agent risk evaluation pipeline has not been executed for your active shipments.
          </p>
          {onRunAnalysis && (
            <button
              onClick={onRunAnalysis}
              disabled={loading}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg shadow-sm transition-all"
            >
              {loading ? "Evaluating Fleet Threats..." : "Run Threat Assessment Now"}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Risk Matrix</h2>
          <p className="text-sm text-slate-500 mt-1">Live threat assessment across active fleet.</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-8">
        {(["HIGH", "MEDIUM", "LOW", "SAFE"] as const).map((level) => {
          const count = riskBreakdown[level];
          const pct = total > 0 ? Math.round((count / total) * 100) : 0;
          
          let color = "text-slate-600 bg-slate-50 border-slate-200";
          let icon = <Shield className="w-5 h-5 text-slate-400" />;
          
          if (level === "HIGH") {
            color = "text-red-700 bg-red-50 border-red-100";
            icon = <ShieldAlert className="w-5 h-5 text-red-500" />;
          } else if (level === "MEDIUM") {
            color = "text-amber-700 bg-amber-50 border-amber-100";
            icon = <AlertTriangle className="w-5 h-5 text-amber-500" />;
          } else if (level === "SAFE") {
            color = "text-emerald-700 bg-emerald-50 border-emerald-100";
            icon = <ShieldCheck className="w-5 h-5 text-emerald-500" />;
          }

          return (
            <div key={level} className={`saas-panel p-5 flex flex-col justify-between h-[115px] border ${color}`}>
              <div className="flex justify-between items-start">
                <div className="text-xs font-semibold uppercase tracking-wider opacity-80">
                  {level} RISK
                </div>
                {icon}
              </div>
              <div className="flex items-end justify-between mt-2">
                <div className="text-3xl font-bold tracking-tight">{count}</div>
                <div className="text-sm font-medium opacity-70">{pct}%</div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="saas-panel overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <th className="px-5 py-4">Shipment ID</th>
              <th className="px-5 py-4">Route Info</th>
              <th className="px-5 py-4">Cargo</th>
              <th className="px-5 py-4">Status</th>
              <th className="px-5 py-4">Risk Level</th>
              <th className="px-5 py-4 text-right">Delay Est.</th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {recommendations.map((r) => {
              let badgeStyle = "bg-slate-100 text-slate-700";
              if (r.risk_level === 'HIGH') badgeStyle = "bg-red-100 text-red-700";
              else if (r.risk_level === 'MEDIUM') badgeStyle = "bg-amber-100 text-amber-800";
              else if (r.risk_level === 'SAFE') badgeStyle = "bg-emerald-100 text-emerald-700";

              return (
                <tr key={r.shipment_id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-4 font-semibold text-slate-900">{r.shipment_id}</td>
                  <td className="px-5 py-4">
                    <div className="text-slate-900 font-medium">{r.origin} &rarr; {r.destination}</div>
                    <div className="text-xs text-slate-500 mt-1">{r.route_highway}</div>
                  </td>
                  <td className="px-5 py-4 text-slate-600">{r.cargo_type}</td>
                  <td className="px-5 py-4">
                    <span className="px-2.5 py-1 text-[11px] font-medium border border-slate-200 rounded-md text-slate-600 bg-white">
                      {r.delivery_priority}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <span className={`px-2.5 py-1 text-[11px] font-bold rounded-full uppercase tracking-wider ${badgeStyle}`}>
                      {r.risk_level}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-right font-medium text-slate-700">
                    {r.estimated_delay_hours ? (
                      <span className="text-amber-600">+{r.estimated_delay_hours} hrs</span>
                    ) : "-"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
