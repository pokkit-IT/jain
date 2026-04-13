import { apiClient } from "./client";
import type { Sale } from "../types";

export interface SaleInput {
  title: string;
  address: string;
  description?: string | null;
  start_date: string;
  end_date?: string | null;
  start_time: string;
  end_time: string;
  tags?: string[];
}

export interface RecentSalesFilter {
  tags?: string[];
  query?: string;
  happeningNow?: boolean;
}

export async function fetchRecentSales(filter: RecentSalesFilter = {}): Promise<Sale[]> {
  const params = new URLSearchParams();
  (filter.tags ?? []).forEach((t) => params.append("tag", t));
  if (filter.query) params.set("q", filter.query);
  if (filter.happeningNow) params.set("happening_now", "1");
  const qs = params.toString();
  const url = qs
    ? `/api/plugins/yardsailing/sales/recent?${qs}`
    : "/api/plugins/yardsailing/sales/recent";
  const res = await apiClient.get<Sale[]>(url);
  return res.data;
}

export async function fetchCuratedTags(): Promise<string[]> {
  const res = await apiClient.get<{ tags: string[] }>("/api/plugins/yardsailing/tags");
  return res.data.tags;
}

export async function fetchMySales(): Promise<Sale[]> {
  const res = await apiClient.get<Sale[]>("/api/plugins/yardsailing/sales");
  return res.data;
}

export async function updateSale(id: string, data: SaleInput): Promise<Sale> {
  const res = await apiClient.put<Sale>(`/api/plugins/yardsailing/sales/${id}`, data);
  return res.data;
}

export async function deleteSale(id: string): Promise<void> {
  await apiClient.delete(`/api/plugins/yardsailing/sales/${id}`);
}
