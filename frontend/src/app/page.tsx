"use client";
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { BACKEND_WS, fetchShipments, fetchDisruptions, fetchRiskAnalysis, runRiskAnalysis } from "@/lib/api";
import type { Shipment, Disruption, RiskAnalysis } from "@/types";
import dynamic from "next/dynamic";
import KpiCard from "@/components/KpiCard";
import Sidebar, { type AppView } from "@/components/Sidebar";
import RiskTable from "@/components/RiskTable";
import DisruptionList from "@/components/DisruptionList";
import RecommendationCards from "@/components/RecommendationCards";
import ShipmentsTab from "@/components/ShipmentsTab";
import SettingsPanel from "@/components/SettingsPanel";
import { Package, AlertCircle, ShieldAlert, ShieldCheck } from "lucide-react";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

const TABS = ["Map View", "Active Fleet", "Anomalies", "Risk Matrix", "AI Strategy"];

export default function DashboardPage() {
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [disruptions, setDisruptions] = useState<Disruption[]>([]);
  const [riskData, setRiskData] = useState<RiskAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [liveUpdate, setLiveUpdate] = useState(false);
  const [tab, setTab] = useState<number>(0);
  const [view, setView] = useState<AppView>("dashboard");
  const [simulatedShipmentId, setSimulatedShipmentId] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [sh, dis, risk] = await Promise.all([
        fetchShipments().catch(() => ({ shipments: [] })),
        fetchDisruptions().catch(() => ({ disruptions: [] })),
        fetchRiskAnalysis().catch(() => null),
      ]);
      setShipments(sh?.shipments || []);
      setDisruptions(dis?.disruptions || []);
      setRiskData(risk);
      setLastUpdated(new Date().toLocaleTimeString("en-IN"));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRunAnalysis = useCallback(async () => {
    setLoading(true);
    try {
      const risk = await runRiskAnalysis();
      setRiskData(risk);
      setLastUpdated(new Date().toLocaleTimeString("en-IN"));
    } catch (err) {
      console.error("Failed to run risk analysis:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      loadAll();
    }
  }, [loadAll, user]);

  useEffect(() => {
    if (view === "dashboard" && (tab === 3 || tab === 4) && !riskData && !loading) {
      handleRunAnalysis();
    }
  }, [tab, view, riskData, loading, handleRunAnalysis]);

  useEffect(() => {
    if (!user) return;
    const token = typeof window !== "undefined" ? sessionStorage.getItem("ws_token") : null;
    const wsUrl = token
      ? `${BACKEND_WS}/ws/risk-updates?token=${encodeURIComponent(token)}`
      : `${BACKEND_WS}/ws/risk-updates`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      if (msg.event === "analysis_complete") {
        setLiveUpdate(true);
        setTimeout(() => setLiveUpdate(false), 4000);
        loadAll();
      }
    };
    ws.onerror = () => {};
    return () => ws.close();
  }, [loadAll, user]);

  const recs = riskData?.recommendations ?? [];
  const pipeline = riskData?.pipeline;
  const rb = pipeline?.risk_breakdown ?? { HIGH: 0, MEDIUM: 0, LOW: 0, SAFE: 0 };

  if (authLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="w-8 h-8 border-4 border-slate-200 border-t-blue-600 rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-50 text-slate-900">
      <Sidebar
        view={view}
        onView={(next) => {
          setView(next);
          if (next === "map") setTab(0);
          if (next === "shipments") setTab(1);
          if (next === "dashboard") setTab(0);
        }}
        onRefresh={loadAll}
        loading={loading}
        lastUpdated={lastUpdated}
      />

      <main className="flex-1 h-screen overflow-y-auto">
        <header className="bg-white border-b border-slate-200 px-8 py-4 flex justify-between items-center sticky top-0 z-10 shadow-sm">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              {view === "settings" ? "Settings" : view === "shipments" ? "Shipments" : "Shipment Overview"}
            </h1>
            <p className="text-sm text-slate-500 font-medium">
              {new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
            </p>
          </div>
          <div className="flex items-center gap-4">
            {liveUpdate && (
              <div className="text-xs font-bold uppercase tracking-widest text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-full flex items-center gap-2 shadow-sm">
                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
                Live Sync
              </div>
            )}
            <button
              onClick={handleRunAnalysis}
              disabled={loading}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors"
            >
              {loading ? "Analyzing..." : "Run analysis"}
            </button>
            <div className="flex items-center gap-2 border border-slate-200 rounded-full py-1.5 px-3 bg-slate-50 shadow-sm">
              <div className="w-6 h-6 bg-blue-600 rounded-full text-white flex items-center justify-center text-xs font-bold">
                {user.name.charAt(0).toUpperCase()}
              </div>
              <span className="text-sm font-semibold text-slate-700">{user.name}</span>
            </div>
          </div>
        </header>

        <div className="p-8 max-w-7xl mx-auto">
          {view === "settings" ? (
            <div className="saas-panel p-8">
              <SettingsPanel onSeeded={loadAll} />
            </div>
          ) : (
            <>
              <div className="grid grid-cols-4 gap-6 mb-8">
                <KpiCard label="Total Shipments" value={shipments.length} icon={<Package className="w-5 h-5 text-blue-500" />} />
                <KpiCard label="Active Anomalies" value={disruptions.length} icon={<AlertCircle className="w-5 h-5 text-indigo-500" />} />
                <KpiCard label="Critical Risk" value={rb.HIGH} icon={<ShieldAlert className="w-5 h-5 text-red-500" />} />
                <KpiCard label="Safe Routes" value={rb.SAFE} icon={<ShieldCheck className="w-5 h-5 text-emerald-500" />} />
              </div>

              {view === "dashboard" && (
                <div className="saas-panel p-2 mb-6 inline-flex gap-1 bg-slate-100/50 shadow-none">
                  {TABS.map((t, i) => (
                    <button
                      key={t}
                      onClick={() => setTab(i)}
                      className={`px-5 py-2 text-sm font-semibold rounded-md transition-all ${
                        tab === i ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-900 hover:bg-slate-200/50"
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              )}

              <div className="saas-panel p-8 min-h-[500px]">
                {loading ? (
                  <div className="flex flex-col items-center justify-center h-64 gap-4">
                    <div className="w-8 h-8 border-4 border-slate-200 border-t-blue-600 rounded-full animate-spin"></div>
                    <div className="text-slate-500 text-sm font-semibold uppercase tracking-widest">Processing Data...</div>
                  </div>
                ) : (
                  <>
                    {view === "map" && (
                      <MapView
                        shipments={shipments}
                        disruptions={disruptions}
                        recommendations={recs}
                        selectedShipmentId={simulatedShipmentId}
                        onClearSimulation={() => setSimulatedShipmentId(null)}
                      />
                    )}
                    {view === "shipments" && <ShipmentsTab shipments={shipments} recommendations={recs} onChanged={loadAll} />}
                    {view === "dashboard" && tab === 0 && (
                      <MapView
                        shipments={shipments}
                        disruptions={disruptions}
                        recommendations={recs}
                        selectedShipmentId={simulatedShipmentId}
                        onClearSimulation={() => setSimulatedShipmentId(null)}
                      />
                    )}
                    {view === "dashboard" && tab === 1 && <ShipmentsTab shipments={shipments} recommendations={recs} onChanged={loadAll} />}
                    {view === "dashboard" && tab === 2 && <DisruptionList disruptions={disruptions} collectorReasoning={pipeline?.collector_reasoning} />}
                    {view === "dashboard" && tab === 3 && <RiskTable recommendations={recs} riskBreakdown={rb} onRunAnalysis={handleRunAnalysis} loading={loading} />}
                    {view === "dashboard" && tab === 4 && (
                      <RecommendationCards
                        recommendations={recs}
                        pipeline={pipeline}
                        onRunAnalysis={handleRunAnalysis}
                        loading={loading}
                        onSimulateRoute={(id) => {
                          setSimulatedShipmentId(id);
                          setTab(0);
                        }}
                      />
                    )}
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
