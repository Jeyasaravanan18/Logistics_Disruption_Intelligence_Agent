"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { changePasswordApi, fetchHealth, seedDemoShipments } from "@/lib/api";

interface Props {
  onSeeded: () => Promise<void> | void;
}

export default function SettingsPanel({ onSeeded }: Props) {
  const { user } = useAuth();
  const [health, setHealth] = useState<{ status?: string; checks?: Record<string, string> } | null>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth({ status: "unreachable" }));
  }, []);

  return (
    <div className="space-y-8 max-w-xl">
      <div>
        <h2 className="text-lg font-bold text-slate-900">Account</h2>
        <p className="text-sm text-slate-500 mt-1">{user?.name} · {user?.email}</p>
      </div>

      <div className="border border-slate-200 rounded-lg p-5">
        <h3 className="font-semibold text-slate-900 mb-3">System health</h3>
        <p className="text-sm text-slate-600 mb-2">API: {health?.status || "checking..."}</p>
        {health?.checks && (
          <ul className="text-sm text-slate-600 space-y-1">
            {Object.entries(health.checks).map(([k, v]) => (
              <li key={k} className="flex justify-between"><span>{k}</span><span className={v === "ok" ? "text-emerald-600" : "text-amber-600"}>{v}</span></li>
            ))}
          </ul>
        )}
      </div>

      <div className="border border-slate-200 rounded-lg p-5">
        <h3 className="font-semibold text-slate-900 mb-2">Demo fleet</h3>
        <p className="text-sm text-slate-500 mb-3">Replace your shipments with the 15-route India demo dataset.</p>
        <button
          className="px-4 py-2 text-sm font-semibold bg-slate-900 text-white rounded-lg disabled:opacity-50"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await seedDemoShipments();
              setMessage("Demo fleet loaded.");
              await onSeeded();
            } catch (e: unknown) {
              setError(e instanceof Error ? e.message : "Seed failed");
            } finally {
              setBusy(false);
            }
          }}
        >
          Load demo shipments
        </button>
      </div>

      <form
        className="border border-slate-200 rounded-lg p-5 space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setError("");
          setMessage("");
          try {
            await changePasswordApi(current, next);
            setMessage("Password updated. Sign in again on other devices.");
            setCurrent("");
            setNext("");
          } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Update failed");
          }
        }}
      >
        <h3 className="font-semibold text-slate-900">Change password</h3>
        <input type="password" required minLength={8} placeholder="Current password" value={current} onChange={(e) => setCurrent(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm" />
        <input type="password" required minLength={8} placeholder="New password (letters + numbers)" value={next} onChange={(e) => setNext(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        {message && <p className="text-sm text-emerald-600">{message}</p>}
        <button className="px-4 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg">Update password</button>
      </form>
    </div>
  );
}
