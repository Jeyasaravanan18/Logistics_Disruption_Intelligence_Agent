"use client";
import { RefreshCw, Box, LayoutDashboard, Truck, Settings, Map as MapIcon, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export type AppView = "dashboard" | "map" | "shipments" | "settings";

interface Props {
  view: AppView;
  onView: (view: AppView) => void;
  onRefresh: () => void;
  loading: boolean;
  lastUpdated: string;
}

export default function Sidebar({ view, onView, onRefresh, loading, lastUpdated }: Props) {
  const { logout } = useAuth();
  return (
    <aside className="w-64 h-screen flex-shrink-0 p-4 flex flex-col justify-between bg-white border-r border-slate-200 sticky top-0 z-20 select-none">
      {/* Brand Header */}
      <div className="mb-6 px-2 flex items-center gap-3">
        <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center text-white shadow-sm shadow-blue-200 flex-shrink-0">
          <Box className="w-5 h-5" />
        </div>
        <div>
          <div className="text-lg font-bold tracking-tight text-slate-900 leading-none">LogiTrack</div>
          <div className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mt-1">Operations Hub</div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 space-y-1 overflow-y-auto pr-1">
        <NavItem icon={<LayoutDashboard className="w-4 h-4" />} label="Dashboard" active={view === "dashboard"} onClick={() => onView("dashboard")} />
        <NavItem icon={<MapIcon className="w-4 h-4" />} label="Map View" active={view === "map"} onClick={() => onView("map")} />
        <NavItem icon={<Truck className="w-4 h-4" />} label="Shipments Fleet" active={view === "shipments"} onClick={() => onView("shipments")} />
        <NavItem icon={<Settings className="w-4 h-4" />} label="Settings" active={view === "settings"} onClick={() => onView("settings")} />
      </nav>

      {/* Action & Footer anchored at bottom */}
      <div className="mt-auto pt-4 flex-shrink-0 space-y-3">
        <button
          onClick={() => logout()}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>

        <button
          onClick={onRefresh}
          disabled={loading}
          className={`w-full py-2.5 px-4 text-sm font-semibold rounded-lg flex items-center justify-center gap-2 border transition-all ${
            loading
              ? "opacity-60 cursor-not-allowed bg-slate-100 text-slate-400 border-slate-200"
              : "bg-slate-900 text-white hover:bg-slate-800 border-transparent shadow-sm"
          }`}
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          {loading ? "Syncing Fleet..." : "Refresh Data"}
        </button>

        <div className="pt-3 border-t border-slate-100 text-[11px] text-slate-400 flex flex-col gap-1.5 px-1">
          {lastUpdated && (
            <div className="flex justify-between">
              <span>Last Sync</span>
              <span className="text-slate-700 font-medium">{lastUpdated}</span>
            </div>
          )}
          <div className="flex justify-between items-center">
            <span>Pipeline Status</span>
            <span className="text-emerald-600 font-medium flex items-center gap-1.5">
              <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
              Live Online
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}

function NavItem({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
        active ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
      }`}
    >
      <span className={active ? "text-blue-600" : "text-slate-400"}>{icon}</span>
      {label}
    </button>
  );
}
