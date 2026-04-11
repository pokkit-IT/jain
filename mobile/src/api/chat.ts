import { apiClient } from "./client";
import { ChatResponse, ChatTurn } from "../types";

export async function sendChatMessage(params: {
  message: string;
  history: ChatTurn[];
  lat?: number;
  lng?: number;
}): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>("/api/chat", params);
  return data;
}
