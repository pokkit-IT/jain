export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ToolEvent {
  name: string;
  arguments: Record<string, unknown>;
}

export interface ChatResponse {
  reply: string;
  data: unknown | null;
  display_hint: string | null;
  tool_events: ToolEvent[];
  choices: string[] | null;
}

export interface PluginHome {
  component: string;
  label: string;
  icon?: string | null;
  description?: string | null;
}

export interface PluginSummary {
  name: string;
  version: string;
  description: string;
  skills: Array<{ name: string; description: string; components?: string[] }>;
  components?: { bundle: string; exports: string[] };
  api?: { base_url: string };
  home?: PluginHome | null;
}

export interface LocationState {
  lat: number;
  lng: number;
}

export interface DayHours {
  day_date: string; // YYYY-MM-DD
  start_time: string; // HH:MM
  end_time: string; // HH:MM
}

export interface SalePhoto {
  id: string;
  position: number;
  content_type: string;
  url: string;       // relative, e.g. "/uploads/sales/<id>/<uuid>.jpg"
  thumb_url: string;
}

export interface Sale {
  id: string;
  owner_id: string;
  title: string;
  address: string;
  lat: number | null;
  lng: number | null;
  description?: string | null;
  start_date?: string;
  end_date?: string | null;
  start_time?: string;
  end_time?: string;
  tags?: string[];
  days?: DayHours[];
  photos?: SalePhoto[];
  source?: "host" | "sighting";
  confirmations?: number;
  groups?: SaleGroupSummary[];
}

export interface SaleGroupSummary {
  id: string;
  name: string;
  slug: string;
  start_date: string | null;
  end_date: string | null;
}

export interface JainUser {
  id: string;
  email: string;
  name: string;
  picture_url: string | null;
}

export interface Session {
  user: JainUser;
  token: string;
}
