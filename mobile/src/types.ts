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

export interface Sale {
  id: number;
  title: string;
  address: string;
  lat: number;
  lng: number;
  description?: string;
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
