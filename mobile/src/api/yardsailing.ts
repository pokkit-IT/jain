import { apiClient } from "./client";
import type { Sale } from "../types";

export async function fetchRecentSales(): Promise<Sale[]> {
  const res = await apiClient.get<Sale[]>("/api/plugins/yardsailing/sales/recent");
  return res.data;
}
