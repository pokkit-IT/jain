import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

const KEY = "jain.access_token";

// expo-secure-store only works on native (iOS Keychain / Android Keystore).
// On web, fall back to localStorage. This is less secure (accessible to JS
// on the same origin), but acceptable for dev testing. Phase 3 hygiene can
// replace this with a more secure option like httpOnly cookies if needed.
const isWeb = Platform.OS === "web";

export async function getToken(): Promise<string | null> {
  try {
    if (isWeb) {
      return typeof window !== "undefined" ? window.localStorage.getItem(KEY) : null;
    }
    return await SecureStore.getItemAsync(KEY);
  } catch {
    return null;
  }
}

export async function setToken(token: string): Promise<void> {
  if (isWeb) {
    if (typeof window !== "undefined") window.localStorage.setItem(KEY, token);
    return;
  }
  await SecureStore.setItemAsync(KEY, token);
}

export async function clearToken(): Promise<void> {
  try {
    if (isWeb) {
      if (typeof window !== "undefined") window.localStorage.removeItem(KEY);
      return;
    }
    await SecureStore.deleteItemAsync(KEY);
  } catch {
    // already gone, ignore
  }
}
