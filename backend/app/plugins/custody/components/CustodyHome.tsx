import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, FlatList, Pressable, RefreshControl,
  ScrollView, StyleSheet, Text, View,
} from "react-native";

import type { Bridge, WithBridge } from "./bridge";

interface Child { id: string; name: string; dob?: string | null }
interface Status {
  state: "with_you" | "away" | "no_schedule";
  since?: string;
  in_care_duration_seconds?: number;
  next_pickup_at?: string;
  last_dropoff_at?: string;
}
interface Event {
  id: string; type: string; occurred_at: string;
  notes?: string | null; location?: string | null;
  amount_cents?: number | null; category?: string | null;
  photos?: { id: string; thumb_url: string }[];
  overnight?: boolean;
}
interface Summary {
  visits_count: number; total_expense_cents: number;
  by_category: Record<string, number>; missed_visits_count: number;
}

const TYPE_COLOR: Record<string, string> = {
  pickup: "#2a7", dropoff: "#888", activity: "#08c",
  expense: "#d90", text_screenshot: "#27b",
  medical: "#c22", school: "#66a", missed_visit: "#d32",
  phone_call: "#6a5", note: "#555",
};
const TYPE_LABEL: Record<string, string> = {
  pickup: "Pickup", dropoff: "Dropoff", activity: "Activity",
  expense: "Expense", text_screenshot: "Text",
  medical: "Medical", school: "School",
  missed_visit: "Missed visit", phone_call: "Call", note: "Note",
};

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatDuration(sec: number) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h === 0) return `${m}m`;
  return `${h}h ${m}m`;
}

function groupByDay(events: Event[]): { label: string; items: Event[] }[] {
  const groups: Record<string, Event[]> = {};
  for (const e of events) {
    const key = e.occurred_at.slice(0, 10);
    (groups[key] ||= []).push(e);
  }
  const today = new Date().toISOString().slice(0, 10);
  const yest = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  return Object.keys(groups)
    .sort()
    .reverse()
    .map((k) => ({
      label: k === today ? "TODAY" : k === yest ? "YESTERDAY" : k,
      items: groups[k],
    }));
}

export function CustodyHome({ bridge }: WithBridge) {
  const [children, setChildren] = useState<Child[]>([]);
  const [childId, setChildId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [missedBanner, setMissedBanner] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadChildren = useCallback(async () => {
    const list = (await bridge.callPluginApi(
      "/api/plugins/custody/children", "GET", null,
    )) as Child[];
    setChildren(list);
    if (list.length && !childId) setChildId(list[0].id);
  }, [bridge, childId]);

  const loadForChild = useCallback(async (id: string) => {
    const refresh = (await bridge.callPluginApi(
      `/api/plugins/custody/schedules/refresh-missed?child_id=${id}`,
      "POST", null,
    )) as { new_rows: number };
    setMissedBanner(refresh?.new_rows || 0);

    const st = (await bridge.callPluginApi(
      `/api/plugins/custody/status?child_id=${id}`, "GET", null,
    )) as Status;
    setStatus(st);

    const now = new Date();
    const ym = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    const sm = (await bridge.callPluginApi(
      `/api/plugins/custody/summary?child_id=${id}&month=${ym}`, "GET", null,
    )) as Summary;
    setSummary(sm);

    const evs = (await bridge.callPluginApi(
      `/api/plugins/custody/events?child_id=${id}&limit=200`, "GET", null,
    )) as Event[];
    setEvents(evs);
  }, [bridge]);

  useEffect(() => { loadChildren().finally(() => setLoading(false)); }, [loadChildren]);
  useEffect(() => { if (childId) loadForChild(childId); }, [childId, loadForChild]);

  const onRefresh = () => {
    if (!childId) return;
    setRefreshing(true);
    loadForChild(childId).finally(() => setRefreshing(false));
  };

  const logQuick = async (type: string) => {
    if (!childId) return;
    await bridge.callPluginApi("/api/plugins/custody/events", "POST", {
      child_id: childId, type, occurred_at: new Date().toISOString(),
    });
    bridge.showToast(`${TYPE_LABEL[type]} logged`);
    loadForChild(childId);
  };

  if (loading) return <ActivityIndicator style={{ marginTop: 40 }} />;
  if (children.length === 0) {
    return (
      <View style={styles.centered}>
        <Text style={styles.heading}>Add a child to get started</Text>
        <Pressable
          style={styles.primaryBtn}
          onPress={() => bridge.openComponent?.("ChildrenScreen")}
        >
          <Text style={styles.primaryBtnText}>Add child</Text>
        </Pressable>
      </View>
    );
  }

  const grouped = groupByDay(events);

  return (
    <FlatList
      data={grouped}
      keyExtractor={(g) => g.label}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      ListHeaderComponent={
        <View>
          {children.length > 1 && (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.childStrip}>
              {children.map((c) => (
                <Pressable
                  key={c.id} onPress={() => setChildId(c.id)}
                  style={[styles.childChip, c.id === childId && styles.childChipActive]}
                >
                  <Text style={c.id === childId ? styles.childChipTextActive : styles.childChipText}>
                    {c.name}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          )}

          {missedBanner > 0 && (
            <View style={styles.banner}>
              <Text style={styles.bannerText}>
                We flagged {missedBanner} missed visit{missedBanner === 1 ? "" : "s"}. Scroll below to review.
              </Text>
            </View>
          )}

          {status?.state === "with_you" && status.since && (
            <View style={[styles.statusCard, { backgroundColor: "#e8f4ee" }]}>
              <Text style={styles.statusLabel}>WITH YOU</Text>
              <Text style={styles.statusName}>
                {children.find((c) => c.id === childId)?.name}
              </Text>
              <Text style={styles.statusSince}>
                Since {formatTime(status.since)} ·
                {" "}{formatDuration(status.in_care_duration_seconds || 0)}
              </Text>
              <Pressable style={styles.primaryBtn} onPress={() => logQuick("dropoff")}>
                <Text style={styles.primaryBtnText}>Dropped off</Text>
              </Pressable>
            </View>
          )}

          {status?.state === "away" && (
            <View style={styles.statusCard}>
              {status.next_pickup_at ? (
                <Text style={styles.statusLabel}>
                  NEXT PICKUP · {new Date(status.next_pickup_at).toLocaleString()}
                </Text>
              ) : (
                <Text style={styles.statusLabel}>No upcoming pickup</Text>
              )}
              {status.last_dropoff_at && (
                <Text style={styles.statusSince}>
                  Last dropoff: {new Date(status.last_dropoff_at).toLocaleString()}
                </Text>
              )}
              <Pressable style={styles.primaryBtn} onPress={() => logQuick("pickup")}>
                <Text style={styles.primaryBtnText}>Picked up</Text>
              </Pressable>
            </View>
          )}

          {status?.state === "no_schedule" && (
            <View style={styles.statusCard}>
              <Text style={styles.statusLabel}>No schedule yet</Text>
              <Pressable
                style={styles.primaryBtn}
                onPress={() => bridge.openComponent?.("ScheduleListScreen")}
              >
                <Text style={styles.primaryBtnText}>Set up schedule</Text>
              </Pressable>
            </View>
          )}

          <View style={styles.quickRow}>
            {[
              { key: "expense", label: "+ Expense", comp: "ExpenseForm" },
              { key: "text_screenshot", label: "+ Text", comp: "TextCaptureForm" },
              { key: "activity", label: "+ Activity", comp: "EventForm", props: { type: "activity" } },
              { key: "note", label: "+ Note", comp: "EventForm", props: { type: "note" } },
            ].map((q) => (
              <Pressable
                key={q.key} style={styles.quickBtn}
                onPress={() =>
                  bridge.openComponent?.(q.comp as string, {
                    childId,
                    ...(q as { props?: Record<string, unknown> }).props,
                  })
                }
              >
                <Text style={styles.quickBtnText}>{q.label}</Text>
              </Pressable>
            ))}
          </View>

          {summary && (
            <View style={styles.summaryStrip}>
              <Text style={styles.summaryText}>
                {summary.visits_count} visits · ${(summary.total_expense_cents / 100).toFixed(0)} spent
                {summary.missed_visits_count > 0 ? ` · ${summary.missed_visits_count} missed` : ""}
              </Text>
            </View>
          )}
        </View>
      }
      renderItem={({ item }) => (
        <View>
          <Text style={styles.dayHeader}>{item.label}</Text>
          {item.items.map((e) => (
            <Pressable
              key={e.id} style={styles.eventRow}
              onPress={() => bridge.openComponent?.("EventForm", { eventId: e.id, mode: "edit" })}
            >
              <View style={[styles.dot, { backgroundColor: TYPE_COLOR[e.type] || "#555" }]} />
              <View style={{ flex: 1 }}>
                <Text style={styles.eventTitle}>
                  {formatTime(e.occurred_at)} · {TYPE_LABEL[e.type] || e.type}
                  {e.type === "expense" && e.amount_cents != null
                    ? ` · $${(e.amount_cents / 100).toFixed(2)}`
                    : ""}
                </Text>
                {e.notes ? <Text style={styles.eventNotes}>{e.notes}</Text> : null}
              </View>
              {e.photos && e.photos.length > 0 ? (
                <Text style={styles.paperclip}>📎</Text>
              ) : null}
            </Pressable>
          ))}
        </View>
      )}
      ListEmptyComponent={
        <Text style={styles.empty}>No events yet. Use the quick actions above.</Text>
      }
    />
  );
}

const styles = StyleSheet.create({
  centered: { padding: 24, alignItems: "center", justifyContent: "center" },
  heading: { fontSize: 18, fontWeight: "600", marginBottom: 12 },
  childStrip: { flexDirection: "row", padding: 8 },
  childChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: "#eee", marginRight: 8 },
  childChipActive: { backgroundColor: "#2a7" },
  childChipText: { color: "#333" },
  childChipTextActive: { color: "#fff", fontWeight: "600" },
  banner: { backgroundColor: "#fff3c0", padding: 10, margin: 10, borderRadius: 6 },
  bannerText: { color: "#6a4f00" },
  statusCard: { margin: 10, padding: 14, borderRadius: 10, backgroundColor: "#f5f5f5" },
  statusLabel: { fontSize: 11, color: "#666", letterSpacing: 1, textTransform: "uppercase" },
  statusName: { fontSize: 22, fontWeight: "700", marginTop: 2 },
  statusSince: { fontSize: 12, color: "#444", marginTop: 2 },
  primaryBtn: { marginTop: 10, backgroundColor: "#2a7", paddingVertical: 10, borderRadius: 8, alignItems: "center" },
  primaryBtnText: { color: "#fff", fontWeight: "600" },
  quickRow: { flexDirection: "row", flexWrap: "wrap", paddingHorizontal: 10 },
  quickBtn: { backgroundColor: "#fff", borderWidth: 1, borderColor: "#ddd", borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6, marginRight: 6, marginBottom: 6 },
  quickBtnText: { fontSize: 13 },
  summaryStrip: { paddingHorizontal: 12, paddingVertical: 6, backgroundColor: "#fafafa" },
  summaryText: { fontSize: 12, color: "#666" },
  dayHeader: { fontSize: 11, color: "#888", letterSpacing: 1, padding: 10, paddingBottom: 4 },
  eventRow: { flexDirection: "row", alignItems: "center", paddingHorizontal: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: "#f0f0f0" },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 10 },
  eventTitle: { fontSize: 13, fontWeight: "600" },
  eventNotes: { fontSize: 12, color: "#666" },
  paperclip: { fontSize: 14 },
  empty: { padding: 24, textAlign: "center", color: "#888" },
});
