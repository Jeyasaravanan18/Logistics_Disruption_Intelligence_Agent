"use client";
import { useState } from "react";
import type { Shipment } from "@/types";
import { CITY_COORDINATES, CITY_NAMES } from "@/lib/cities";

interface Props {
  initial?: Shipment | null;
  onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => Promise<void>;
}

export default function ShipmentForm({ initial, onClose, onSubmit }: Props) {
  const [shipmentId, setShipmentId] = useState(initial?.shipment_id || "");
  const [origin, setOrigin] = useState(initial?.origin || "Chennai");
  const [destination, setDestination] = useState(initial?.destination || "Madurai");
  const [routeHighway, setRouteHighway] = useState(initial?.route_highway || "NH44");
  const [priority, setPriority] = useState(initial?.delivery_priority || "MEDIUM");
  const [cargo, setCargo] = useState(initial?.cargo_type || "");
  const [weight, setWeight] = useState(initial?.weight_kg?.toString() || "");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const applyOrigin = (city: string) => {
    setOrigin(city);
    const coords = CITY_COORDINATES[city];
    if (coords) {
      /* coords applied at submit */
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSaving(true);
    const coords = CITY_COORDINATES[origin] || { lat: initial?.latitude || 20.59, lon: initial?.longitude || 78.96 };
    try {
      await onSubmit({
        ...(initial ? {} : { shipment_id: shipmentId.trim() }),
        origin,
        destination,
        route_highway: routeHighway.trim(),
        delivery_priority: priority,
        cargo_type: cargo.trim() || null,
        weight_kg: weight ? Number(weight) : null,
        latitude: coords.lat,
        longitude: coords.lon,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaving(false);
      return;
    }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
        <h3 className="text-lg font-bold text-slate-900 mb-4">
          {initial ? `Edit ${initial.shipment_id}` : "New shipment"}
        </h3>
        {error && <div className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-2">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-3">
          {!initial && (
            <label className="block text-sm font-medium text-slate-700">
              Shipment ID
              <input required value={shipmentId} onChange={(e) => setShipmentId(e.target.value)} className="mt-1 w-full border rounded-lg px-3 py-2 text-sm" placeholder="S200" />
            </label>
          )}
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm font-medium text-slate-700">
              Origin
              <select value={origin} onChange={(e) => applyOrigin(e.target.value)} className="mt-1 w-full border rounded-lg px-3 py-2 text-sm">
                {CITY_NAMES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Destination
              <select value={destination} onChange={(e) => setDestination(e.target.value)} className="mt-1 w-full border rounded-lg px-3 py-2 text-sm">
                {CITY_NAMES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
          </div>
          <label className="block text-sm font-medium text-slate-700">
            Highway
            <input required value={routeHighway} onChange={(e) => setRouteHighway(e.target.value)} className="mt-1 w-full border rounded-lg px-3 py-2 text-sm" />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm font-medium text-slate-700">
              Priority
              <select value={priority} onChange={(e) => setPriority(e.target.value as Shipment["delivery_priority"])} className="mt-1 w-full border rounded-lg px-3 py-2 text-sm">
                <option>HIGH</option>
                <option>MEDIUM</option>
                <option>LOW</option>
              </select>
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Weight (kg)
              <input type="number" min={0} value={weight} onChange={(e) => setWeight(e.target.value)} className="mt-1 w-full border rounded-lg px-3 py-2 text-sm" />
            </label>
          </div>
          <label className="block text-sm font-medium text-slate-700">
            Cargo type
            <input value={cargo} onChange={(e) => setCargo(e.target.value)} className="mt-1 w-full border rounded-lg px-3 py-2 text-sm" placeholder="Pharmaceuticals" />
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm rounded-lg border">Cancel</button>
            <button type="submit" disabled={saving} className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white font-semibold disabled:opacity-50">
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
