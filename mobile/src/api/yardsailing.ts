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
}

export async function fetchRecentSales(): Promise<Sale[]> {
  const res = await apiClient.get<Sale[]>("/api/plugins/yardsailing/sales/recent");
  return res.data;
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
