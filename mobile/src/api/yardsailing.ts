import { apiClient } from "./client";
import type { Sale, SaleGroupSummary, SalePhoto } from "../types";

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
  groupId?: string;
}

export async function fetchRecentSales(filter: RecentSalesFilter = {}): Promise<Sale[]> {
  const params = new URLSearchParams();
  (filter.tags ?? []).forEach((t) => params.append("tag", t));
  if (filter.query) params.set("q", filter.query);
  if (filter.happeningNow) params.set("happening_now", "1");
  if (filter.groupId) params.set("group_id", filter.groupId);
  const qs = params.toString();
  const url = qs
    ? `/api/plugins/yardsailing/sales/recent?${qs}`
    : "/api/plugins/yardsailing/sales/recent";
  const res = await apiClient.get<Sale[]>(url);
  return res.data;
}

export async function postSighting(
  lat: number, lng: number, nowHHMM: string,
): Promise<Sale> {
  const { data } = await apiClient.post<Sale>(
    "/api/plugins/yardsailing/sightings",
    { lat, lng, now_hhmm: nowHHMM },
  );
  return data;
}

export async function fetchGroups(query: string = ""): Promise<SaleGroupSummary[]> {
  const url = query
    ? `/api/plugins/yardsailing/groups?q=${encodeURIComponent(query)}`
    : "/api/plugins/yardsailing/groups";
  const res = await apiClient.get<SaleGroupSummary[]>(url);
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

export async function uploadSalePhoto(
  saleId: string,
  file: { uri: string; name: string; type: string },
): Promise<SalePhoto> {
  const form = new FormData();
  // React Native FormData accepts {uri, name, type} for local file uploads.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form.append("file", file as any);
  const { data } = await apiClient.post<SalePhoto>(
    `/api/plugins/yardsailing/sales/${saleId}/photos`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function deleteSalePhoto(saleId: string, photoId: string): Promise<void> {
  await apiClient.delete(
    `/api/plugins/yardsailing/sales/${saleId}/photos/${photoId}`,
  );
}

export async function reorderSalePhotos(
  saleId: string,
  photoIds: string[],
): Promise<SalePhoto[]> {
  const { data } = await apiClient.patch<SalePhoto[]>(
    `/api/plugins/yardsailing/sales/${saleId}/photos/reorder`,
    { photo_ids: photoIds },
  );
  return data;
}

export interface RouteStop {
  sale_id: string;
  eta_minutes: number;
  in_window: boolean;
  title: string;
  address: string;
  lat: number;
  lng: number;
}

export interface Route {
  stops: RouteStop[];
  total_distance_miles: number;
  total_duration_minutes: number;
}

export interface PlanRouteResponse {
  route: Route;
}

export async function planRoute(
  saleIds: string[],
  start: { lat: number; lng: number },
): Promise<PlanRouteResponse> {
  const { data } = await apiClient.post<PlanRouteResponse>(
    "/api/plugins/yardsailing/plan_route",
    { sale_ids: saleIds, start_location: start },
  );
  return data;
}
