import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";

const FALLBACK_TAGS = [
  "Furniture", "Toys", "Tools", "Baby Items", "Clothing",
  "Books", "Electronics", "Kitchen", "Sports", "Garden",
  "Holiday", "Art", "Free",
];

export interface DayHours {
  day_date: string;
  start_time: string;
  end_time: string;
}

export interface SaleFormData {
  title: string;
  description: string;
  address: string;
  start_date: string;
  end_date: string;
  start_time: string;
  end_time: string;
  tags: string[];
  days: DayHours[];
}

function datesInRange(startIso: string, endIso: string): string[] {
  if (!startIso) return [];
  const start = new Date(startIso + "T00:00:00");
  if (isNaN(start.getTime())) return [];
  const end = endIso ? new Date(endIso + "T00:00:00") : start;
  if (isNaN(end.getTime()) || end < start) return [startIso];
  const out: string[] = [];
  const cur = new Date(start);
  while (cur <= end) {
    out.push(cur.toISOString().slice(0, 10));
    cur.setDate(cur.getDate() + 1);
  }
  return out;
}

export interface SaleFormProps {
  initialData?: Partial<SaleFormData>;
  bridge: {
    callPluginApi: (path: string, method: string, body: unknown) => Promise<unknown>;
    closeComponent: () => void;
    showToast: (msg: string) => void;
  };
}

const EMPTY: SaleFormData = {
  title: "",
  description: "",
  address: "",
  start_date: "",
  end_date: "",
  start_time: "",
  end_time: "",
  tags: [],
  days: [],
};

export function SaleForm({ initialData, bridge }: SaleFormProps) {
  const [data, setData] = useState<SaleFormData>({ ...EMPTY, ...initialData });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [tagVocab, setTagVocab] = useState<string[]>(FALLBACK_TAGS);

  useEffect(() => {
    // Pull the curated list from the server so the vocabulary stays in
    // sync without a rebuild. Fall back to the baked-in list on failure.
    bridge
      .callPluginApi("/api/plugins/yardsailing/tags", "GET", null)
      .then((res) => {
        const tags = (res as { tags?: string[] })?.tags;
        if (Array.isArray(tags) && tags.length > 0) setTagVocab(tags);
      })
      .catch(() => { /* keep fallback */ });
  }, [bridge]);

  const set = <K extends keyof SaleFormData>(key: K, value: SaleFormData[K]) =>
    setData((d) => ({ ...d, [key]: value }));

  const rangeDates = datesInRange(data.start_date, data.end_date);
  const multiDay = rangeDates.length > 1;

  const setDayHours = (day: string, startT: string, endT: string) => {
    setData((d) => {
      const others = d.days.filter((x) => x.day_date !== day);
      // Only store an override if it differs from the defaults.
      const isDefault = startT === d.start_time && endT === d.end_time;
      const next = isDefault
        ? others
        : [...others, { day_date: day, start_time: startT, end_time: endT }];
      return { ...d, days: next };
    });
  };

  const toggleTag = (tag: string) => {
    setData((d) => ({
      ...d,
      tags: d.tags.includes(tag)
        ? d.tags.filter((t) => t !== tag)
        : [...d.tags, tag],
    }));
  };

  const submit = async () => {
    // eslint-disable-next-line no-console
    console.log("[SaleForm] submit pressed, data =", data);
    setError(null);
    setSuccess(null);

    const missing: string[] = [];
    if (!data.title) missing.push("title");
    if (!data.address) missing.push("address");
    if (!data.start_date) missing.push("start date");
    if (!data.start_time) missing.push("start time");
    if (!data.end_time) missing.push("end time");

    if (missing.length > 0) {
      const msg = `Missing required: ${missing.join(", ")}`;
      // eslint-disable-next-line no-console
      console.log("[SaleForm] validation failed:", msg);
      setError(msg);
      return;
    }

    setSubmitting(true);
    try {
      // eslint-disable-next-line no-console
      console.log("[SaleForm] calling bridge.callPluginApi");
      const result = await bridge.callPluginApi("/api/plugins/yardsailing/sales", "POST", data);
      // eslint-disable-next-line no-console
      console.log("[SaleForm] bridge returned:", result);
      setSuccess("Yard sale created!");
      bridge.showToast("Yard sale created!");
      // Give the user a beat to see the success message before closing
      setTimeout(() => bridge.closeComponent(), 800);
    } catch (e) {
      const msg = (e as Error).message || "Failed to create sale";
      // eslint-disable-next-line no-console
      console.log("[SaleForm] bridge error:", msg, e);
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.header}>Create Yard Sale</Text>

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {success ? (
        <View style={styles.successBox}>
          <Text style={styles.successText}>{success}</Text>
        </View>
      ) : null}

      <Text style={styles.label}>Title *</Text>
      <TextInput
        style={styles.input}
        value={data.title}
        onChangeText={(v) => set("title", v)}
        placeholder="Big Saturday Sale"
      />

      <Text style={styles.label}>Address *</Text>
      <TextInput
        style={styles.input}
        value={data.address}
        onChangeText={(v) => set("address", v)}
        placeholder="123 Main St"
      />

      <Text style={styles.label}>Description</Text>
      <TextInput
        style={[styles.input, styles.multiline]}
        value={data.description}
        onChangeText={(v) => set("description", v)}
        placeholder="What you're selling..."
        multiline
      />

      <View style={styles.row}>
        <View style={styles.half}>
          <Text style={styles.label}>Start Date *</Text>
          <TextInput
            style={styles.input}
            value={data.start_date}
            onChangeText={(v) => set("start_date", v)}
            placeholder="2026-04-11"
          />
        </View>
        <View style={styles.half}>
          <Text style={styles.label}>End Date</Text>
          <TextInput
            style={styles.input}
            value={data.end_date}
            onChangeText={(v) => set("end_date", v)}
            placeholder="2026-04-11"
          />
        </View>
      </View>

      <View style={styles.row}>
        <View style={styles.half}>
          <Text style={styles.label}>
            {multiDay ? "Default Start Time *" : "Start Time *"}
          </Text>
          <TextInput
            style={styles.input}
            value={data.start_time}
            onChangeText={(v) => set("start_time", v)}
            placeholder="08:00"
          />
        </View>
        <View style={styles.half}>
          <Text style={styles.label}>
            {multiDay ? "Default End Time *" : "End Time *"}
          </Text>
          <TextInput
            style={styles.input}
            value={data.end_time}
            onChangeText={(v) => set("end_time", v)}
            placeholder="14:00"
          />
        </View>
      </View>

      {multiDay ? (
        <>
          <Text style={styles.label}>Per-day hours</Text>
          <Text style={styles.hint}>
            Adjust any day if hours differ from the defaults above.
          </Text>
          {rangeDates.map((d) => {
            const override = data.days.find((x) => x.day_date === d);
            const st = override?.start_time ?? data.start_time;
            const et = override?.end_time ?? data.end_time;
            return (
              <View key={d} style={styles.dayRow}>
                <Text style={styles.dayDate}>{d}</Text>
                <TextInput
                  style={[styles.input, styles.dayInput]}
                  value={st}
                  onChangeText={(v) => setDayHours(d, v, et)}
                  placeholder="08:00"
                />
                <Text style={styles.dayDash}>–</Text>
                <TextInput
                  style={[styles.input, styles.dayInput]}
                  value={et}
                  onChangeText={(v) => setDayHours(d, st, v)}
                  placeholder="14:00"
                />
              </View>
            );
          })}
        </>
      ) : null}

      <Text style={styles.label}>Tags</Text>
      <View style={styles.tagRow}>
        {tagVocab.map((tag) => {
          const active = data.tags.includes(tag);
          return (
            <TouchableOpacity
              key={tag}
              onPress={() => toggleTag(tag)}
              style={[styles.tagChip, active && styles.tagChipActive]}
            >
              <Text style={[styles.tagText, active && styles.tagTextActive]}>
                {tag}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <TouchableOpacity
        style={[styles.button, submitting && styles.buttonDisabled]}
        onPress={submit}
        disabled={submitting}
      >
        <Text style={styles.buttonText}>
          {submitting ? "Creating..." : "Create Sale"}
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, backgroundColor: "#fff" },
  header: { fontSize: 22, fontWeight: "600", marginBottom: 16 },
  label: { fontSize: 14, fontWeight: "500", marginTop: 12, marginBottom: 4 },
  input: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    padding: 10,
    fontSize: 16,
  },
  multiline: { minHeight: 80, textAlignVertical: "top" },
  row: { flexDirection: "row", gap: 8 },
  half: { flex: 1 },
  button: {
    backgroundColor: "#2563eb",
    padding: 14,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 20,
    marginBottom: 40,
  },
  buttonDisabled: { backgroundColor: "#94a3b8" },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  errorBox: {
    backgroundColor: "#fee2e2",
    borderWidth: 1,
    borderColor: "#fca5a5",
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  errorText: { color: "#b91c1c", fontSize: 14, fontWeight: "500" },
  successBox: {
    backgroundColor: "#d1fae5",
    borderWidth: 1,
    borderColor: "#6ee7b7",
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  successText: { color: "#065f46", fontSize: 14, fontWeight: "500" },
  tagRow: { flexDirection: "row", flexWrap: "wrap", marginTop: 4 },
  tagChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#cbd5e1",
    backgroundColor: "#f8fafc",
    marginRight: 6,
    marginBottom: 6,
  },
  tagChipActive: { backgroundColor: "#2563eb", borderColor: "#2563eb" },
  tagText: { fontSize: 13, color: "#334155", fontWeight: "600" },
  tagTextActive: { color: "#fff" },
  hint: { fontSize: 12, color: "#64748b", marginBottom: 8 },
  dayRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 6,
    gap: 6,
  },
  dayDate: {
    width: 110,
    fontSize: 13,
    fontWeight: "600",
    color: "#334155",
  },
  dayInput: { flex: 1, paddingVertical: 6 },
  dayDash: { color: "#94a3b8", fontSize: 14 },
});
