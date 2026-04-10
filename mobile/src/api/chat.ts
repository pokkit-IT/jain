import { apiClient } from "./client";
import { ChatResponse, ChatTurn } from "../types";

export async function sendChatMessage(params: {
  message: string;
  history: ChatTurn[];
  lat?: number;
  lng?: number;
  auth?: Record<string, boolean>;
}): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>("/api/chat", params);
  return data;
}
