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

export interface PluginSummary {
  name: string;
  version: string;
  description: string;
  skills: Array<{ name: string; description: string; components?: string[] }>;
  components?: { bundle: string; exports: string[] };
  api?: { base_url: string };
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

export interface Sale {
  id: string;
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
