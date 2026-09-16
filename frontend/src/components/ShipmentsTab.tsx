"use client";
import { useState } from "react";
import type { Shipment, Recommendation } from "@/types";
import ShipmentForm from "./ShipmentForm";
import { createShipment, updateShipment, deleteShipment } from "@/lib/api";

interface Props {
  shipments: Shipment[];
  recommendations: Recommendation[];
  onChanged: () => Promise<void> | void;
}

export default function ShipmentsTab({ shipments, recommendations, onChanged }: Props) {
  const [formFor, setFormFor] = useState<Shipment | null | "new">(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const riskLookup = Object.fromEntries(recommendations.map((r) => [r.shipment_id, r.risk_level]));

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-bold text-slate-900">Fleet shipments</h2>
        <button onClick={() => setFormFor("new")} className="px-4 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg">
          Add shipment
        </button>
      </div>
      <div className="w-full overflow-x-auto border border-slate-200 rounded-lg">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <th className="p-4">Shipment ID</th>
              <th className="p-4">Route</th>
              <th className="p-4">Cargo</th>
              <th className="p-4">Priority</th>
              <th className="p-4">Status</th>
              <th className="p-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {shipments.length === 0 && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-slate-500">No shipments yet. Add one or seed the demo fleet in Settings.</td>
              </tr>
            )}
            {shipments.map((s) => {
              const rl = riskLookup[s.shipment_id] ?? "SAFE";
              let badgeStyle = "bg-slate-100 text-slate-700";
              if (rl === "HIGH") badgeStyle = "bg-red-100 text-red-700";
              else if (rl === "MEDIUM") badgeStyle = "bg-amber-100 text-amber-800";
              else if (rl === "SAFE") badgeStyle = "bg-emerald-100 text-emerald-700";
              return (
                <tr key={s.shipment_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="p-4 font-semibold text-slate-900">{s.shipment_id}</td>
                  <td className="p-4 text-slate-600 font-medium">
                    {s.origin} &rarr; {s.destination}
                    <span className="block text-xs text-slate-400 mt-0.5">{s.route_highway}</span>
                  </td>
                  <td className="p-4 text-slate-600">{s.cargo_type || "—"}</td>
                  <td className="p-4 text-slate-600">{s.delivery_priority}</td>
                  <td className="p-4">
                    <span className={`px-2.5 py-1 text-[11px] font-bold rounded-full uppercase tracking-wider ${badgeStyle}`}>{rl}</span>
                  </td>
                  <td className="p-4 text-right space-x-2">
                    <button className="text-blue-600 text-xs font-semibold" onClick={() => setFormFor(s)}>Edit</button>
                    <button
                      className="text-red-600 text-xs font-semibold disabled:opacity-50"
                      disabled={busyId === s.shipment_id}
                      onClick={async () => {
                        if (!confirm(`Delete ${s.shipment_id}?`)) return;
                        setBusyId(s.shipment_id);
                        try {
                          await deleteShipment(s.shipment_id);
                          await onChanged();
                        } finally {
                          setBusyId(null);
                        }
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {formFor !== null && (
        <ShipmentForm
          initial={formFor === "new" ? null : formFor}
          onClose={() => setFormFor(null)}
          onSubmit={async (payload) => {
            if (formFor === "new") {
              await createShipment(payload);
            } else {
              const { shipment_id: _id, ...rest } = payload;
              await updateShipment(formFor.shipment_id, rest);
            }
            setFormFor(null);
            await onChanged();
          }}
        />
      )}
    </div>
  );
}
