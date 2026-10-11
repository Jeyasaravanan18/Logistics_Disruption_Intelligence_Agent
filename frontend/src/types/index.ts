export interface Shipment {
  shipment_id: string;
  origin: string;
  destination: string;
  route_highway: string;
  latitude: number;
  longitude: number;
  delivery_priority: "HIGH" | "MEDIUM" | "LOW";
  estimated_delivery_time?: string;
  cargo_type?: string;
  weight_kg?: number;
}

export interface Disruption {
  id: string;
  type: "weather" | "news";
  subtype: string;
  location: string;
  lat: number;
  lon: number;
  severity: "HIGH" | "MEDIUM" | "LOW";
  description: string;
  source: string;
  data_source?: "live_api" | "demo_fixture" | string;
  timestamp: string;
  impact_duration_hours?: number;
}

export interface Recommendation {
  shipment_id: string;
  origin: string;
  destination: string;
  route_highway: string;
  cargo_type: string;
  delivery_priority: string;
  risk_level: "HIGH" | "MEDIUM" | "LOW" | "SAFE";
  risk_score: number;
  reason: string;
  suggested_action: string;
  alternate_route?: string;
  estimated_delay_hours?: number;
  customer_message?: string;
  disruption_type?: string;
  disruption_location?: string;
  distance_to_disruption_km?: number;
}

export interface AgentTraceItem {
  id?: string;
  node: string;
  started_at: string;
  duration_ms: number;
  input_hash?: string;
  output_summary: string;
  used_llm: boolean;
  fallback_used: boolean;
  tokens_estimate?: number;
  error?: string | null;
}

export interface PipelineInfo {
  run_id?: string;
  disruptions_collected: number;
  shipments_evaluated: number;
  risk_breakdown: { HIGH: number; MEDIUM: number; LOW: number; SAFE: number };
  collector_reasoning: string;
  traces?: AgentTraceItem[];
}

export interface RiskAnalysis {
  pipeline: PipelineInfo;
  recommendations: Recommendation[];
}

