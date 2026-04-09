import { apiClient } from "./client";
import { PluginSummary } from "../types";

export async function listPlugins(): Promise<PluginSummary[]> {
  const { data } = await apiClient.get<{ plugins: PluginSummary[] }>("/api/plugins");
  return data.plugins;
}
