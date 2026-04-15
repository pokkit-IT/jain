import axios from "axios";
import { Platform } from "react-native";

import { getToken } from "../auth/tokenStorage";

const DEV_HOST = Platform.OS === "android" ? "10.0.2.2" : "localhost";
const API_BASE =
  process.env.EXPO_PUBLIC_JAIN_API_URL ?? `http://${DEV_HOST}:8000`;

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
});

// Attach the JAIN JWT to every outgoing request when present.
apiClient.interceptors.request.use(async (config) => {
  const token = await getToken();
  if (token) {
    config.headers = config.headers ?? {};
    (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  return config;
});

export function absUrl(relative: string): string {
  if (/^https?:\/\//.test(relative)) return relative;
  const base = apiClient.defaults.baseURL ?? "";
  // baseURL may or may not include /api — the server returns paths starting with /uploads/
  // We want: <origin><relative>. Strip any path suffix from baseURL to get origin.
  try {
    const url = new URL(base);
    return `${url.protocol}//${url.host}${relative}`;
  } catch {
    return `${base}${relative}`;
  }
}
