"use client";
import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Circle, Polyline } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { Shipment, Disruption, Recommendation } from "@/types";

interface Props {
  shipments: Shipment[];
  disruptions: Disruption[];
  recommendations: Recommendation[];
  selectedShipmentId?: string | null;
  onClearSimulation?: () => void;
}

const CITY_COORDS: Record<string, [number, number]> = {
  "delhi": [28.6139, 77.2090],
  "new delhi": [28.6139, 77.2090],
  "mumbai": [19.0760, 72.8777],
  "navi mumbai": [19.0330, 73.0297],
  "bengaluru": [12.9716, 77.5946],
  "bangalore": [12.9716, 77.5946],
  "chennai": [13.0827, 80.2707],
  "kolkata": [22.5726, 88.3639],
  "hyderabad": [17.3850, 78.4867],
  "pune": [18.5204, 73.8567],
  "ahmedabad": [23.0225, 72.5714],
  "jaipur": [26.9124, 75.7873],
  "surat": [21.1702, 72.8311],
  "lucknow": [26.8467, 80.9462],
  "kanpur": [26.4499, 80.3319],
  "nagpur": [21.1458, 79.0882],
  "indore": [22.7196, 75.8577],
  "bhopal": [23.2599, 77.4126],
  "patna": [25.5941, 85.1376],
  "vadodara": [22.3072, 73.1812],
  "ghaziabad": [28.6692, 77.4538],
  "ludhiana": [30.9010, 75.8573],
  "agra": [27.1767, 78.0081],
  "nashik": [19.9975, 73.7898],
  "varanasi": [25.3176, 82.9739],
  "amritsar": [31.6340, 74.8723],
  "chandigarh": [30.7333, 76.7794],
  "coimbatore": [11.0168, 76.9558],
  "visakhapatnam": [17.6868, 83.2185],
  "guwahati": [26.1445, 91.7362],
  "kochi": [9.9312, 76.2673],
  "cochin": [9.9312, 76.2673],
  "jabalpur": [23.1815, 79.9864],
  "gwalior": [26.2183, 78.1828],
  "vijayawada": [16.5062, 80.6480],
  "jodhpur": [26.2389, 73.0243],
  "madurai": [9.9252, 78.1198],
  "raipur": [21.2514, 81.6296],
  "kota": [25.2138, 75.8648],
  "ranchi": [23.3441, 85.3096],
  "bhubaneswar": [20.2961, 85.8245],
  "thiruvananthapuram": [8.5241, 76.9366],
  "trivandrum": [8.5241, 76.9366],
  "jamshedpur": [22.8046, 86.2029],
  "dehradun": [30.3165, 78.0322],
  "noida": [28.5355, 77.3910],
  "gurgaon": [28.4595, 77.0266],
  "gurugram": [28.4595, 77.0266],
  "panipat": [29.3909, 76.9635],
  "karnal": [29.6857, 76.9905],
  "bathinda": [30.2110, 74.9455],
  "panvel": [18.9894, 73.1175],
  "haldia": [22.0667, 88.0698],
  "gandhidham": [23.0753, 70.1337],
  "mundra": [22.8394, 69.7266],
  "nhava sheva": [18.9500, 72.9500],
  "tiruppur": [11.1085, 77.3411],
  "salem": [11.6643, 78.1460],
  "mangalore": [12.9141, 74.8560],
  "mysore": [12.2958, 76.6394],
  "hubli": [15.3647, 75.1240],
  "belgaum": [15.8497, 74.4977],
  "aurangabad": [19.8762, 75.3433],
  "solapur": [17.6599, 75.9064],
  "kolhapur": [16.7050, 74.2433],
  "udaipur": [24.5854, 73.7125],
  "bikaner": [28.0229, 73.3119],
  "ajmer": [26.4499, 74.6399],
  "mathura": [27.4924, 77.6737],
  "moradabad": [28.8386, 78.7733],
  "bareilly": [28.3670, 79.4304],
  "aligarh": [27.8974, 78.0880],
  "gorakhpur": [26.7606, 83.3732],
  "prayagraj": [25.4358, 81.8463],
  "allahabad": [25.4358, 81.8463],
  "goa": [15.2993, 74.1240],
};

function getCityCoord(name?: string): [number, number] | null {
  if (!name) return null;
  const key = name.trim().toLowerCase();
  if (CITY_COORDS[key]) return CITY_COORDS[key];
  for (const [k, coords] of Object.entries(CITY_COORDS)) {
    if (key.includes(k) || k.includes(key)) {
      return coords;
    }
  }
  return null;
}

const STRATEGIC_DETOURS: Record<string, { viaName: string; coords: [number, number][] }> = {
  "chennai-madurai": {
    viaName: "Tiruchirappalli (Trichy) Bypass via NH38",
    coords: [[10.7905, 78.7047]],
  },
  "mumbai-pune": {
    viaName: "Panvel-Khopoli Diversion via Old Highway",
    coords: [[18.9894, 73.1175], [18.7865, 73.3421]],
  },
  "delhi-jaipur": {
    viaName: "Delhi-Mumbai Expressway (NE4) via Dausa",
    coords: [[28.3180, 77.0600], [26.8920, 76.3350]],
  },
  "bangalore-hyderabad": {
    viaName: "Anantapur-Kurnool Bypass via NH40",
    coords: [[14.6819, 77.6006], [15.8281, 78.0373]],
  },
  "kolkata-bhubaneswar": {
    viaName: "Kharagpur-Balasore Bypass via NH60",
    coords: [[22.3460, 87.2320], [21.4934, 86.9135]],
  },
  "delhi-lucknow": {
    viaName: "Yamuna & Agra-Lucknow Expressway Corridor",
    coords: [[27.1767, 78.0081], [27.0200, 79.5000]],
  },
  "ahmedabad-mumbai": {
    viaName: "Vadodara-Surat Industrial Bypass via NE1",
    coords: [[22.3072, 73.1812], [21.1702, 72.8311]],
  },
  "delhi-chandigarh": {
    viaName: "Western Peripheral Expressway (WPE) via NH152D",
    coords: [[28.7500, 76.8000], [29.9000, 76.6000]],
  },
  "indore-bhopal": {
    viaName: "Dewas-Ashta 4-Lane State Expressway",
    coords: [[22.9676, 76.0534], [23.0180, 76.5430]],
  },
  "surat-vadodara": {
    viaName: "Bharuch-Ankleshwar Golden Bridge Diversion",
    coords: [[21.6264, 73.0033]],
  },
};

function getDetourPath(
  originName: string,
  destName: string,
  originCoord: [number, number],
  destCoord: [number, number]
): { viaName: string; path: [number, number][]; waypoints: [number, number][] } {
  const oKey = (originName || "").trim().toLowerCase();
  const dKey = (destName || "").trim().toLowerCase();
  const directKey = `${oKey}-${dKey}`;
  const reverseKey = `${dKey}-${oKey}`;

  if (STRATEGIC_DETOURS[directKey]) {
    const d = STRATEGIC_DETOURS[directKey];
    return {
      viaName: d.viaName,
      path: [originCoord, ...d.coords, destCoord],
      waypoints: d.coords,
    };
  }
  if (STRATEGIC_DETOURS[reverseKey]) {
    const d = STRATEGIC_DETOURS[reverseKey];
    const rev = [...d.coords].reverse();
    return {
      viaName: d.viaName,
      path: [originCoord, ...rev, destCoord],
      waypoints: rev,
    };
  }

  const midLat = (originCoord[0] + destCoord[0]) / 2;
  const midLon = (originCoord[1] + destCoord[1]) / 2;
  const dLat = destCoord[0] - originCoord[0];
  const dLon = destCoord[1] - originCoord[1];
  const offsetLat = midLat - dLon * 0.22;
  const offsetLon = midLon + dLat * 0.22;
  const detourPoint: [number, number] = [offsetLat, offsetLon];

  return {
    viaName: "Regional Outer Ring / State Highway Diversion",
    path: [originCoord, detourPoint, destCoord],
    waypoints: [detourPoint],
  };
}

export default function MapView({
  shipments,
  disruptions,
  recommendations,
  selectedShipmentId,
  onClearSimulation,
}: Props) {
  const [LInstance, setLInstance] = useState<any>(null);
  const [diversionConfirmed, setDiversionConfirmed] = useState(false);

  useEffect(() => {
    import("leaflet").then((leaflet) => {
      setLInstance(leaflet.default || leaflet);
    });
  }, []);

  // Reset confirmation state if selected shipment changes
  useEffect(() => {
    setDiversionConfirmed(false);
  }, [selectedShipmentId]);

  if (!LInstance) {
    return (
      <div className="h-[520px] w-full flex items-center justify-center text-slate-500 text-sm saas-panel">
        Loading Map Engine...
      </div>
    );
  }

  const createIcon = (color: string) => {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="${color}" width="24" height="24" stroke="white" stroke-width="2"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>`;
    return LInstance.divIcon({
      className: "custom-icon",
      html: svg,
      iconSize: [28, 28],
      iconAnchor: [14, 28],
      popupAnchor: [0, -28],
    });
  };

  const waypointIcon = LInstance.divIcon({
    className: "waypoint-icon",
    html: `<div style="background:#0284c7;width:12px;height:12px;border-radius:50%;border:2px solid white;box-shadow:0 0 8px rgba(2,132,199,0.9)"></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });

  const shipIconSafe = createIcon("#10b981"); // emerald-500
  const shipIconWarning = createIcon("#f59e0b"); // amber-500
  const shipIconRisk = createIcon("#ef4444"); // red-500
  const disruptionIcon = createIcon("#6366f1"); // indigo-500

  const getRisk = (id: string) => recommendations.find((r) => r.shipment_id === id)?.risk_level || "SAFE";

  // Active Simulation Details
  const simShipment = selectedShipmentId ? shipments.find((s) => s.shipment_id === selectedShipmentId) : null;
  const simRec = selectedShipmentId ? recommendations.find((r) => r.shipment_id === selectedShipmentId) : null;
  const simOriginCoord = simShipment ? getCityCoord(simShipment.origin) : null;
  const simDestCoord = simShipment ? getCityCoord(simShipment.destination) : null;
  const detourInfo =
    simShipment && simOriginCoord && simDestCoord
      ? getDetourPath(simShipment.origin, simShipment.destination, simOriginCoord, simDestCoord)
      : null;

  return (
    <div className="h-[540px] w-full rounded-xl overflow-hidden saas-panel p-0 relative shadow-md">
      <MapContainer center={[20.5937, 78.9629]} zoom={5} className="h-full w-full">
        {/* Modern Carto Voyager light tile layer */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
        />

        {/* Render Disruptions as pulsing zones */}
        {disruptions.map((d) => {
          const lat = (d as any).latitude ?? (d as any).lat;
          const lon = (d as any).longitude ?? (d as any).lon;
          if (typeof lat !== "number" || typeof lon !== "number" || isNaN(lat) || isNaN(lon)) {
            return null;
          }
          const radius = Number((d as any).radius_km || 30) * 1000;

          return (
            <Circle
              key={d.id}
              center={[lat, lon]}
              radius={radius}
              pathOptions={{ color: "#6366f1", fillColor: "#6366f1", fillOpacity: 0.15, weight: 2, dashArray: "4 4" }}
            >
              <Marker position={[lat, lon]} icon={disruptionIcon}>
                <Popup>
                  <div className="p-1">
                    <div className="font-bold text-sm text-slate-900 mb-1">{d.subtype}</div>
                    <div className="text-xs text-slate-500 mb-2">{d.location}</div>
                    <div className="text-xs text-slate-700">{d.description}</div>
                  </div>
                </Popup>
              </Marker>
            </Circle>
          );
        })}

        {/* Render Route Corridor Polylines */}
        {shipments.map((s) => {
          const currentLat = s.latitude;
          const currentLon = s.longitude;
          if (typeof currentLat !== "number" || typeof currentLon !== "number" || isNaN(currentLat) || isNaN(currentLon)) {
            return null;
          }

          const originCoord = getCityCoord(s.origin);
          const destCoord = getCityCoord(s.destination);
          const currentCoord: [number, number] = [currentLat, currentLon];

          const points: [number, number][] = [];
          if (originCoord) {
            const distFromOrigin = Math.hypot(originCoord[0] - currentLat, originCoord[1] - currentLon);
            if (distFromOrigin > 0.1) {
              points.push(originCoord);
            }
          }
          points.push(currentCoord);
          if (destCoord) {
            const distFromDest = Math.hypot(destCoord[0] - currentLat, destCoord[1] - currentLon);
            if (distFromDest > 0.1) {
              points.push(destCoord);
            }
          }

          if (points.length < 2) return null;

          const isSimulated = s.shipment_id === selectedShipmentId;
          const risk = getRisk(s.shipment_id);
          const lineColor = isSimulated ? "#dc2626" : risk === "HIGH" ? "#ef4444" : risk === "MEDIUM" ? "#f59e0b" : "#10b981";
          const dash = isSimulated ? "6 6" : risk === "HIGH" ? "6 6" : risk === "MEDIUM" ? "4 4" : undefined;
          const weight = isSimulated ? 4.5 : risk === "HIGH" ? 3.5 : risk === "MEDIUM" ? 3 : 2.5;

          return (
            <Polyline
              key={`line-${s.shipment_id}`}
              positions={points}
              pathOptions={{
                color: lineColor,
                dashArray: dash,
                weight: weight,
                opacity: isSimulated ? 0.9 : 0.6,
              }}
            >
              <Popup>
                <div className="p-1">
                  <div className="font-bold text-xs text-slate-900 mb-0.5">{s.shipment_id} - Primary Corridor</div>
                  <div className="text-[11px] text-slate-600 font-medium">{s.origin} &rarr; {s.destination}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Route: {s.route_highway}</div>
                  <div className={`text-[10px] font-semibold mt-1 ${risk === "HIGH" ? "text-red-600" : risk === "MEDIUM" ? "text-amber-600" : "text-emerald-600"}`}>
                    Corridor Risk: {risk}
                  </div>
                </div>
              </Popup>
            </Polyline>
          );
        })}

        {/* Render Proposed Alternate Detour Route when Simulated */}
        {detourInfo && (
          <>
            <Polyline
              positions={detourInfo.path}
              pathOptions={{
                color: "#0284c7", // Sky/Cyan electric detour line
                weight: 5,
                opacity: 0.95,
                dashArray: "8 6",
              }}
            >
              <Popup>
                <div className="p-1.5 max-w-xs">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-sky-700 mb-1">
                    <span className="w-2 h-2 rounded-full bg-sky-500 animate-ping"></span>
                    PROPOSED DETOUR CORRIDOR
                  </div>
                  <div className="text-xs font-semibold text-slate-800 mb-1">{detourInfo.viaName}</div>
                  <div className="text-[11px] text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-1.5 py-0.5 font-medium mt-1">
                    Recovers ~{simRec?.estimated_delay_hours ? `${simRec.estimated_delay_hours} hrs` : "4-6 hrs"} delay vs primary bottleneck
                  </div>
                </div>
              </Popup>
            </Polyline>
            {detourInfo.waypoints.map((wp, idx) => (
              <Marker key={`detour-wp-${idx}`} position={wp} icon={waypointIcon}>
                <Popup>
                  <div className="p-1 text-xs">
                    <span className="font-bold text-sky-700">Bypass Waypoint #{idx + 1}</span>
                    <p className="text-slate-600 mt-0.5">{detourInfo.viaName}</p>
                  </div>
                </Popup>
              </Marker>
            ))}
          </>
        )}

        {/* Render Shipments Live Markers */}
        {shipments.map((s) => {
          const lat = s.latitude;
          const lon = s.longitude;
          if (typeof lat !== "number" || typeof lon !== "number" || isNaN(lat) || isNaN(lon)) {
            return null;
          }
          const risk = getRisk(s.shipment_id);
          const icon = risk === "HIGH" ? shipIconRisk : risk === "MEDIUM" ? shipIconWarning : shipIconSafe;
          const bg = risk === "HIGH" ? "bg-red-50 text-red-700 border-red-200" : risk === "MEDIUM" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-emerald-50 text-emerald-700 border-emerald-200";

          return (
            <Marker key={s.shipment_id} position={[lat, lon]} icon={icon}>
              <Popup>
                <div className="p-1">
                  <div className="font-bold text-sm text-slate-900 flex justify-between items-center mb-2 gap-4">
                    {s.shipment_id}
                    <span className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 border rounded-full ${bg}`}>
                      {risk}
                    </span>
                  </div>
                  <div className="text-xs text-slate-600 font-medium">
                    {s.origin} &rarr; {s.destination}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono mt-1">
                    Route: {s.route_highway}
                  </div>
                  <div className="text-[10px] mt-2 pt-2 border-t border-slate-100 text-slate-500">
                    Cargo: {s.cargo_type || "General Freight"}
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      {/* Floating What-If Route Simulator HUD */}
      {selectedShipmentId && simShipment && (
        <div className="absolute top-4 right-4 z-[400] w-84 bg-white/95 backdrop-blur-md border border-sky-300 rounded-xl shadow-xl p-4 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2 mb-3">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-500 animate-ping"></span>
              <span className="text-xs font-bold uppercase tracking-wider text-sky-800">What-If Route Simulator</span>
            </div>
            {onClearSimulation && (
              <button
                onClick={onClearSimulation}
                className="text-slate-400 hover:text-slate-700 text-xs font-bold p-1 rounded transition-colors"
                title="Exit Simulator"
              >
                ✕
              </button>
            )}
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between items-center">
              <span className="font-mono font-bold text-slate-900">{simShipment.shipment_id}</span>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-red-100 text-red-700 border border-red-200">
                Disrupted
              </span>
            </div>

            <div className="bg-slate-50 border border-slate-100 rounded-lg p-2.5 space-y-2">
              <div>
                <span className="text-[10px] uppercase font-semibold text-slate-500 block mb-0.5">Primary Corridor (Bottlenecked)</span>
                <span className="text-slate-800 font-medium text-xs flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-500 inline-block"></span>
                  {simShipment.route_highway} ({simShipment.origin} &rarr; {simShipment.destination})
                </span>
                {simRec?.estimated_delay_hours && (
                  <span className="text-[10px] text-red-600 block mt-0.5">
                    Est. Delay: +{simRec.estimated_delay_hours} hrs
                  </span>
                )}
              </div>

              <div className="border-t border-slate-200/80 pt-2">
                <span className="text-[10px] uppercase font-semibold text-sky-600 block mb-0.5">Proposed Detour Bypass</span>
                <span className="text-sky-900 font-medium text-xs flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-sky-500 inline-block"></span>
                  {detourInfo ? detourInfo.viaName : (simRec?.alternate_route || "Strategic bypass corridor")}
                </span>
                <div className="text-[10px] text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-2 py-1 mt-1.5 flex items-center justify-between font-semibold">
                  <span>Averts Major Bottlenecks</span>
                  <span>Saves ~{simRec?.estimated_delay_hours || 4} hrs</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => setDiversionConfirmed(!diversionConfirmed)}
              className={`w-full py-2 px-3 rounded-lg text-xs font-semibold shadow-sm transition-all duration-150 flex items-center justify-center gap-2 ${
                diversionConfirmed
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                  : "bg-sky-600 hover:bg-sky-700 text-white"
              }`}
            >
              {diversionConfirmed ? (
                <>
                  <span>✓</span> Diversion Protocol Confirmed
                </>
              ) : (
                <>
                  <span>⚡</span> Confirm Diversion Protocol
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Map Legend */}
      <div className="absolute bottom-4 left-4 z-[400] bg-white/95 backdrop-blur-sm border border-slate-200 p-3 rounded-lg text-xs font-medium text-slate-600 flex flex-col gap-2 shadow-lg">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-emerald-500 rounded-full border border-emerald-600"></div>
          <span>Safe Shipment / Corridor</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-amber-500 rounded-full border border-amber-600"></div>
          <span>Medium Risk Route</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-red-500 rounded-full border border-red-600"></div>
          <span>High Risk Corridor</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-5 h-1 bg-sky-500 rounded-full"></div>
          <span className="text-sky-700 font-semibold">Alternate Detour Bypass</span>
        </div>
        <div className="flex items-center gap-2 mt-1 pt-1 border-t border-slate-100">
          <div className="w-3 h-3 border border-dashed border-indigo-500 rounded-full flex items-center justify-center bg-indigo-50">
            <div className="w-1 h-1 bg-indigo-500 rounded-full"></div>
          </div>
          <span>Active Disruption Zone</span>
        </div>
      </div>
    </div>
  );
}

