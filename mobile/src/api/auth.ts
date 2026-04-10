import { apiClient } from "./client";
import { JainUser, Session } from "../types";

interface GoogleAuthResponse {
  access_token: string;
  user: JainUser;
}

export async function signInWithGoogle(idToken: string): Promise<Session> {
  const { data } = await apiClient.post<GoogleAuthResponse>(
    "/api/auth/google",
    { id_token: idToken },
  );
  return { user: data.user, token: data.access_token };
}

export async function fetchCurrentUser(): Promise<JainUser> {
  const { data } = await apiClient.get<JainUser>("/api/auth/me");
  return data;
}
