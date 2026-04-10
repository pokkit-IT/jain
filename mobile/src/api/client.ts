import axios from "axios";
import { Platform } from "react-native";

const DEV_HOST = Platform.OS === "android" ? "10.0.2.2" : "localhost";
const API_BASE =
  process.env.EXPO_PUBLIC_JAIN_API_URL ?? `http://${DEV_HOST}:8000`;

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
});
