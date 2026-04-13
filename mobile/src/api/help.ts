import { apiClient } from "./client";

export interface HelpExample {
  prompt: string;
  description: string;
}

export interface PluginHelp {
  name: string;
  version: string;
  description: string;
  help_markdown: string;
  examples: HelpExample[];
}

export async function fetchPluginHelp(): Promise<PluginHelp[]> {
  const res = await apiClient.get<{ plugins: PluginHelp[] }>("/api/plugins/help");
  return res.data.plugins;
}
