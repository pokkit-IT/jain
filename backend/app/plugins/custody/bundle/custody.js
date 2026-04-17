(() => {
  var __create = Object.create;
  var __defProp = Object.defineProperty;
  var __defProps = Object.defineProperties;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropDescs = Object.getOwnPropertyDescriptors;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __getOwnPropSymbols = Object.getOwnPropertySymbols;
  var __getProtoOf = Object.getPrototypeOf;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __propIsEnum = Object.prototype.propertyIsEnumerable;
  var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
  var __spreadValues = (a, b) => {
    for (var prop in b || (b = {}))
      if (__hasOwnProp.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    if (__getOwnPropSymbols)
      for (var prop of __getOwnPropSymbols(b)) {
        if (__propIsEnum.call(b, prop))
          __defNormalProp(a, prop, b[prop]);
      }
    return a;
  };
  var __spreadProps = (a, b) => __defProps(a, __getOwnPropDescs(b));
  var __require = /* @__PURE__ */ ((x) => typeof require !== "undefined" ? require : typeof Proxy !== "undefined" ? new Proxy(x, {
    get: (a, b) => (typeof require !== "undefined" ? require : a)[b]
  }) : x)(function(x) {
    if (typeof require !== "undefined") return require.apply(this, arguments);
    throw Error('Dynamic require of "' + x + '" is not supported');
  });
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toESM = (mod) => mod;
  var __async = (__this, __arguments, generator) => {
    return new Promise((resolve, reject) => {
      var fulfilled = (value) => {
        try {
          step(generator.next(value));
        } catch (e) {
          reject(e);
        }
      };
      var rejected = (value) => {
        try {
          step(generator.throw(value));
        } catch (e) {
          reject(e);
        }
      };
      var step = (x) => x.done ? resolve(x.value) : Promise.resolve(x.value).then(fulfilled, rejected);
      step((generator = generator.apply(__this, __arguments)).next());
    });
  };

  // components/ChildrenScreen.tsx
  var import_react = __toESM(__require("react"), 1);
  var import_react_native = __require("react-native");
  function ChildrenScreen({ bridge }) {
    const [children, setChildren] = (0, import_react.useState)([]);
    const [loading, setLoading] = (0, import_react.useState)(true);
    const [name, setName] = (0, import_react.useState)("");
    const [dob, setDob] = (0, import_react.useState)("");
    const load = () => __async(this, null, function* () {
      setLoading(true);
      const rows = yield bridge.callPluginApi(
        "/api/plugins/custody/children",
        "GET",
        null
      );
      setChildren(rows);
      setLoading(false);
    });
    (0, import_react.useEffect)(() => {
      load();
    }, []);
    const add = () => __async(this, null, function* () {
      if (!name.trim()) return;
      yield bridge.callPluginApi("/api/plugins/custody/children", "POST", {
        name: name.trim(),
        dob: dob.trim() || null
      });
      setName("");
      setDob("");
      bridge.showToast("Added");
      load();
    });
    const remove = (c) => __async(this, null, function* () {
      import_react_native.Alert.alert("Delete child?", `All events for ${c.name} will be deleted.`, [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => __async(this, null, function* () {
            yield bridge.callPluginApi(`/api/plugins/custody/children/${c.id}`, "DELETE", null);
            load();
          })
        }
      ]);
    });
    if (loading) return /* @__PURE__ */ import_react.default.createElement(import_react_native.ActivityIndicator, { style: { marginTop: 40 } });
    return /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.container }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.title }, "Children"), /* @__PURE__ */ import_react.default.createElement(
      import_react_native.FlatList,
      {
        data: children,
        keyExtractor: (c) => c.id,
        renderItem: ({ item }) => /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.row }, /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: { flex: 1 } }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.name }, item.name), item.dob && /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.dob }, "DOB ", item.dob)), /* @__PURE__ */ import_react.default.createElement(import_react_native.Pressable, { onPress: () => remove(item) }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: { color: "#c22" } }, "Delete")))
      }
    ), /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "Add a child"), /* @__PURE__ */ import_react.default.createElement(import_react_native.TextInput, { style: styles.input, placeholder: "Name", value: name, onChangeText: setName }), /* @__PURE__ */ import_react.default.createElement(import_react_native.TextInput, { style: styles.input, placeholder: "DOB (YYYY-MM-DD, optional)", value: dob, onChangeText: setDob }), /* @__PURE__ */ import_react.default.createElement(import_react_native.Pressable, { style: styles.primary, onPress: add }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.primaryText }, "Add")));
  }
  var styles = import_react_native.StyleSheet.create({
    container: { padding: 16 },
    title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
    row: { flexDirection: "row", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#f0f0f0" },
    name: { fontSize: 16 },
    dob: { fontSize: 12, color: "#666" },
    label: { fontSize: 12, color: "#666", marginTop: 16, marginBottom: 6, letterSpacing: 0.5, textTransform: "uppercase" },
    input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, marginBottom: 8 },
    primary: { backgroundColor: "#2a7", padding: 12, borderRadius: 6, alignItems: "center", marginTop: 4 },
    primaryText: { color: "#fff", fontWeight: "600" }
  });

  // components/CustodyHome.tsx
  var import_react2 = __toESM(__require("react"), 1);
  var import_react_native2 = __require("react-native");
  var TYPE_COLOR = {
    pickup: "#2a7",
    dropoff: "#888",
    activity: "#08c",
    expense: "#d90",
    text_screenshot: "#27b",
    medical: "#c22",
    school: "#66a",
    missed_visit: "#d32",
    phone_call: "#6a5",
    note: "#555"
  };
  var TYPE_LABEL = {
    pickup: "Pickup",
    dropoff: "Dropoff",
    activity: "Activity",
    expense: "Expense",
    text_screenshot: "Text",
    medical: "Medical",
    school: "School",
    missed_visit: "Missed visit",
    phone_call: "Call",
    note: "Note"
  };
  function formatTime(iso) {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  function formatDuration(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor(sec % 3600 / 60);
    if (h === 0) return `${m}m`;
    return `${h}h ${m}m`;
  }
  function groupByDay(events) {
    const groups = {};
    for (const e of events) {
      const key = e.occurred_at.slice(0, 10);
      (groups[key] || (groups[key] = [])).push(e);
    }
    const today = (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
    const yest = new Date(Date.now() - 864e5).toISOString().slice(0, 10);
    return Object.keys(groups).sort().reverse().map((k) => ({
      label: k === today ? "TODAY" : k === yest ? "YESTERDAY" : k,
      items: groups[k]
    }));
  }
  function CustodyHome({ bridge }) {
    var _a;
    const [children, setChildren] = (0, import_react2.useState)([]);
    const [childId, setChildId] = (0, import_react2.useState)(null);
    const [status, setStatus] = (0, import_react2.useState)(null);
    const [summary, setSummary] = (0, import_react2.useState)(null);
    const [events, setEvents] = (0, import_react2.useState)([]);
    const [missedBanner, setMissedBanner] = (0, import_react2.useState)(0);
    const [loading, setLoading] = (0, import_react2.useState)(true);
    const [refreshing, setRefreshing] = (0, import_react2.useState)(false);
    const loadChildren = (0, import_react2.useCallback)(() => __async(this, null, function* () {
      const list = yield bridge.callPluginApi(
        "/api/plugins/custody/children",
        "GET",
        null
      );
      setChildren(list);
      if (list.length && !childId) setChildId(list[0].id);
    }), [bridge, childId]);
    const loadForChild = (0, import_react2.useCallback)((id) => __async(this, null, function* () {
      const refresh = yield bridge.callPluginApi(
        `/api/plugins/custody/schedules/refresh-missed?child_id=${id}`,
        "POST",
        null
      );
      setMissedBanner((refresh == null ? void 0 : refresh.new_rows) || 0);
      const st = yield bridge.callPluginApi(
        `/api/plugins/custody/status?child_id=${id}`,
        "GET",
        null
      );
      setStatus(st);
      const now = /* @__PURE__ */ new Date();
      const ym = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
      const sm = yield bridge.callPluginApi(
        `/api/plugins/custody/summary?child_id=${id}&month=${ym}`,
        "GET",
        null
      );
      setSummary(sm);
      const evs = yield bridge.callPluginApi(
        `/api/plugins/custody/events?child_id=${id}&limit=200`,
        "GET",
        null
      );
      setEvents(evs);
    }), [bridge]);
    (0, import_react2.useEffect)(() => {
      loadChildren().finally(() => setLoading(false));
    }, [loadChildren]);
    (0, import_react2.useEffect)(() => {
      if (childId) loadForChild(childId);
    }, [childId, loadForChild]);
    const onRefresh = () => {
      if (!childId) return;
      setRefreshing(true);
      loadForChild(childId).finally(() => setRefreshing(false));
    };
    const logQuick = (type) => __async(this, null, function* () {
      if (!childId) return;
      yield bridge.callPluginApi("/api/plugins/custody/events", "POST", {
        child_id: childId,
        type,
        occurred_at: (/* @__PURE__ */ new Date()).toISOString()
      });
      bridge.showToast(`${TYPE_LABEL[type]} logged`);
      loadForChild(childId);
    });
    if (loading) return /* @__PURE__ */ import_react2.default.createElement(import_react_native2.ActivityIndicator, { style: { marginTop: 40 } });
    if (children.length === 0) {
      return /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: styles2.centered }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.heading }, "Add a child to get started"), /* @__PURE__ */ import_react2.default.createElement(
        import_react_native2.Pressable,
        {
          style: styles2.primaryBtn,
          onPress: () => {
            var _a2;
            return (_a2 = bridge.openComponent) == null ? void 0 : _a2.call(bridge, "ChildrenScreen");
          }
        },
        /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.primaryBtnText }, "Add child")
      ));
    }
    const grouped = groupByDay(events);
    return /* @__PURE__ */ import_react2.default.createElement(
      import_react_native2.FlatList,
      {
        data: grouped,
        keyExtractor: (g) => g.label,
        refreshControl: /* @__PURE__ */ import_react2.default.createElement(import_react_native2.RefreshControl, { refreshing, onRefresh }),
        ListHeaderComponent: /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, null, children.length > 1 && /* @__PURE__ */ import_react2.default.createElement(import_react_native2.ScrollView, { horizontal: true, showsHorizontalScrollIndicator: false, style: styles2.childStrip }, children.map((c) => /* @__PURE__ */ import_react2.default.createElement(
          import_react_native2.Pressable,
          {
            key: c.id,
            onPress: () => setChildId(c.id),
            style: [styles2.childChip, c.id === childId && styles2.childChipActive]
          },
          /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: c.id === childId ? styles2.childChipTextActive : styles2.childChipText }, c.name)
        ))), missedBanner > 0 && /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: styles2.banner }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.bannerText }, "We flagged ", missedBanner, " missed visit", missedBanner === 1 ? "" : "s", ". Scroll below to review.")), (status == null ? void 0 : status.state) === "with_you" && status.since && /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: [styles2.statusCard, { backgroundColor: "#e8f4ee" }] }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.statusLabel }, "WITH YOU"), /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.statusName }, (_a = children.find((c) => c.id === childId)) == null ? void 0 : _a.name), /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.statusSince }, "Since ", formatTime(status.since), " \xB7", " ", formatDuration(status.in_care_duration_seconds || 0)), /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Pressable, { style: styles2.primaryBtn, onPress: () => logQuick("dropoff") }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.primaryBtnText }, "Dropped off"))), (status == null ? void 0 : status.state) === "away" && /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: styles2.statusCard }, status.next_pickup_at ? /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.statusLabel }, "NEXT PICKUP \xB7 ", new Date(status.next_pickup_at).toLocaleString()) : /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.statusLabel }, "No upcoming pickup"), status.last_dropoff_at && /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.statusSince }, "Last dropoff: ", new Date(status.last_dropoff_at).toLocaleString()), /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Pressable, { style: styles2.primaryBtn, onPress: () => logQuick("pickup") }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.primaryBtnText }, "Picked up"))), (status == null ? void 0 : status.state) === "no_schedule" && /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: styles2.statusCard }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.statusLabel }, "No schedule yet"), /* @__PURE__ */ import_react2.default.createElement(
          import_react_native2.Pressable,
          {
            style: styles2.primaryBtn,
            onPress: () => {
              var _a2;
              return (_a2 = bridge.openComponent) == null ? void 0 : _a2.call(bridge, "ScheduleListScreen");
            }
          },
          /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.primaryBtnText }, "Set up schedule")
        )), /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: styles2.quickRow }, [
          { key: "expense", label: "+ Expense", comp: "ExpenseForm" },
          { key: "text_screenshot", label: "+ Text", comp: "TextCaptureForm" },
          { key: "activity", label: "+ Activity", comp: "EventForm", props: { type: "activity" } },
          { key: "note", label: "+ Note", comp: "EventForm", props: { type: "note" } }
        ].map((q) => /* @__PURE__ */ import_react2.default.createElement(
          import_react_native2.Pressable,
          {
            key: q.key,
            style: styles2.quickBtn,
            onPress: () => {
              var _a2;
              return (_a2 = bridge.openComponent) == null ? void 0 : _a2.call(bridge, q.comp, __spreadValues({
                childId
              }, q.props));
            }
          },
          /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.quickBtnText }, q.label)
        ))), summary && /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: styles2.summaryStrip }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.summaryText }, summary.visits_count, " visits \xB7 $", (summary.total_expense_cents / 100).toFixed(0), " spent", summary.missed_visits_count > 0 ? ` \xB7 ${summary.missed_visits_count} missed` : ""))),
        renderItem: ({ item }) => /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, null, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.dayHeader }, item.label), item.items.map((e) => /* @__PURE__ */ import_react2.default.createElement(
          import_react_native2.Pressable,
          {
            key: e.id,
            style: styles2.eventRow,
            onPress: () => {
              var _a2;
              return (_a2 = bridge.openComponent) == null ? void 0 : _a2.call(bridge, "EventForm", { eventId: e.id, mode: "edit" });
            }
          },
          /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: [styles2.dot, { backgroundColor: TYPE_COLOR[e.type] || "#555" }] }),
          /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: { flex: 1 } }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.eventTitle }, formatTime(e.occurred_at), " \xB7 ", TYPE_LABEL[e.type] || e.type, e.type === "expense" && e.amount_cents != null ? ` \xB7 $${(e.amount_cents / 100).toFixed(2)}` : ""), e.notes ? /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.eventNotes }, e.notes) : null),
          e.photos && e.photos.length > 0 ? /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.paperclip }, "\u{1F4CE}") : null
        ))),
        ListEmptyComponent: /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.empty }, "No events yet. Use the quick actions above.")
      }
    );
  }
  var styles2 = import_react_native2.StyleSheet.create({
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
    empty: { padding: 24, textAlign: "center", color: "#888" }
  });

  // components/EventForm.tsx
  var import_react3 = __toESM(__require("react"), 1);
  var import_react_native3 = __require("react-native");
  function EventForm({ bridge, childId, type = "note", eventId, mode = "create" }) {
    const [effectiveType, setEffectiveType] = (0, import_react3.useState)(type);
    const [occurredAt, setOccurredAt] = (0, import_react3.useState)(() => (/* @__PURE__ */ new Date()).toISOString());
    const [notes, setNotes] = (0, import_react3.useState)("");
    const [location, setLocation] = (0, import_react3.useState)("");
    const [overnight, setOvernight] = (0, import_react3.useState)(false);
    const [callConnected, setCallConnected] = (0, import_react3.useState)(true);
    const [saving, setSaving] = (0, import_react3.useState)(false);
    const [deleting, setDeleting] = (0, import_react3.useState)(false);
    const [error, setError] = (0, import_react3.useState)(null);
    const [loaded, setLoaded] = (0, import_react3.useState)(mode === "create");
    (0, import_react3.useEffect)(() => {
      if (mode !== "edit" || !eventId) return;
      bridge.callPluginApi(`/api/plugins/custody/events/${eventId}`, "GET", null).catch(() => __async(this, null, function* () {
        const list = yield bridge.callPluginApi(
          `/api/plugins/custody/events?limit=500`,
          "GET",
          null
        );
        return list.find((x) => x.id === eventId);
      })).then((evt) => {
        var _a;
        if (!evt) return;
        const e = evt;
        setEffectiveType(e.type);
        setOccurredAt(e.occurred_at);
        setNotes(e.notes || "");
        setLocation(e.location || "");
        setOvernight(!!e.overnight);
        setCallConnected((_a = e.call_connected) != null ? _a : true);
      }).finally(() => setLoaded(true));
    }, [bridge, eventId, mode]);
    const save = () => __async(this, null, function* () {
      setSaving(true);
      setError(null);
      try {
        if (mode === "edit" && eventId) {
          yield bridge.callPluginApi(`/api/plugins/custody/events/${eventId}`, "PATCH", __spreadProps(__spreadValues(__spreadValues({
            notes: notes || null,
            location: location || null
          }, effectiveType === "pickup" ? { overnight } : {}), effectiveType === "phone_call" ? { call_connected: callConnected } : {}), {
            occurred_at: occurredAt
          }));
        } else {
          if (!childId) {
            setError("Missing child id.");
            setSaving(false);
            return;
          }
          yield bridge.callPluginApi("/api/plugins/custody/events", "POST", {
            child_id: childId,
            type: effectiveType,
            occurred_at: occurredAt,
            notes: notes || null,
            location: location || null,
            overnight: effectiveType === "pickup" ? overnight : false,
            call_connected: effectiveType === "phone_call" ? callConnected : null
          });
        }
        bridge.showToast("Saved");
        bridge.closeComponent();
      } catch (e) {
        setError(e.message || "Failed to save");
      } finally {
        setSaving(false);
      }
    });
    const remove = () => __async(this, null, function* () {
      if (!eventId) return;
      setDeleting(true);
      try {
        yield bridge.callPluginApi(`/api/plugins/custody/events/${eventId}`, "DELETE", null);
        bridge.showToast("Deleted");
        bridge.closeComponent();
      } catch (e) {
        setError(e.message || "Failed to delete");
      } finally {
        setDeleting(false);
      }
    });
    if (!loaded) return /* @__PURE__ */ import_react3.default.createElement(import_react_native3.ActivityIndicator, { style: { marginTop: 40 } });
    return /* @__PURE__ */ import_react3.default.createElement(import_react_native3.View, { style: styles3.container }, /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Text, { style: styles3.title }, mode === "edit" ? "Edit event" : `Log ${effectiveType.replace("_", " ")}`), /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Text, { style: styles3.label }, "When (ISO)"), /* @__PURE__ */ import_react3.default.createElement(import_react_native3.TextInput, { style: styles3.input, value: occurredAt, onChangeText: setOccurredAt }), /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Text, { style: styles3.label }, "Notes"), /* @__PURE__ */ import_react3.default.createElement(
      import_react_native3.TextInput,
      {
        style: [styles3.input, { height: 70 }],
        multiline: true,
        value: notes,
        onChangeText: setNotes
      }
    ), /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Text, { style: styles3.label }, "Location"), /* @__PURE__ */ import_react3.default.createElement(import_react_native3.TextInput, { style: styles3.input, value: location, onChangeText: setLocation }), effectiveType === "pickup" && /* @__PURE__ */ import_react3.default.createElement(import_react_native3.View, { style: styles3.switchRow }, /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Text, { style: styles3.label }, "Overnight visit"), /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Switch, { value: overnight, onValueChange: setOvernight })), effectiveType === "phone_call" && /* @__PURE__ */ import_react3.default.createElement(import_react_native3.View, { style: styles3.switchRow }, /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Text, { style: styles3.label }, "Call connected"), /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Switch, { value: callConnected, onValueChange: setCallConnected })), error && /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Text, { style: styles3.error }, error), /* @__PURE__ */ import_react3.default.createElement(import_react_native3.View, { style: styles3.btnRow }, /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Pressable, { style: styles3.cancelBtn, onPress: bridge.closeComponent }, /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Text, { style: styles3.cancelBtnText }, "Cancel")), /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Pressable, { style: styles3.saveBtn, onPress: save, disabled: saving }, saving ? /* @__PURE__ */ import_react3.default.createElement(import_react_native3.ActivityIndicator, { color: "#fff" }) : /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Text, { style: styles3.saveBtnText }, "Save"))), mode === "edit" && /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Pressable, { style: styles3.deleteBtn, onPress: remove, disabled: deleting }, /* @__PURE__ */ import_react3.default.createElement(import_react_native3.Text, { style: styles3.deleteBtnText }, deleting ? "Deleting..." : "Delete event")));
  }
  var styles3 = import_react_native3.StyleSheet.create({
    container: { padding: 16 },
    title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
    label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
    input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 14 },
    switchRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 10 },
    error: { color: "#c22", marginTop: 10 },
    btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
    cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
    cancelBtnText: { fontWeight: "600", color: "#444" },
    saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
    saveBtnText: { color: "#fff", fontWeight: "600" },
    deleteBtn: { marginTop: 20, padding: 10, alignItems: "center" },
    deleteBtnText: { color: "#c22", fontWeight: "600" }
  });

  // components/ExpenseForm.tsx
  var import_react4 = __toESM(__require("react"), 1);
  var import_react_native4 = __require("react-native");
  var CATEGORIES = ["food", "activity", "clothing", "school", "medical", "other"];
  function ExpenseForm({ bridge, childId }) {
    const [amount, setAmount] = (0, import_react4.useState)("");
    const [description, setDescription] = (0, import_react4.useState)("");
    const [category, setCategory] = (0, import_react4.useState)("activity");
    const [saving, setSaving] = (0, import_react4.useState)(false);
    const [error, setError] = (0, import_react4.useState)(null);
    const save = () => __async(this, null, function* () {
      const parsed = parseFloat(amount);
      if (Number.isNaN(parsed) || parsed <= 0) {
        setError("Enter a dollar amount.");
        return;
      }
      setError(null);
      setSaving(true);
      try {
        yield bridge.callPluginApi("/api/plugins/custody/events", "POST", {
          child_id: childId,
          type: "expense",
          occurred_at: (/* @__PURE__ */ new Date()).toISOString(),
          amount_cents: Math.round(parsed * 100),
          category,
          notes: description.trim() || null
        });
        bridge.showToast(`$${parsed.toFixed(2)} logged`);
        bridge.closeComponent();
      } catch (e) {
        setError(e.message || "Failed to save");
      } finally {
        setSaving(false);
      }
    });
    return /* @__PURE__ */ import_react4.default.createElement(import_react_native4.View, { style: styles4.container }, /* @__PURE__ */ import_react4.default.createElement(import_react_native4.Text, { style: styles4.title }, "Log expense"), /* @__PURE__ */ import_react4.default.createElement(import_react_native4.Text, { style: styles4.label }, "Amount (USD)"), /* @__PURE__ */ import_react4.default.createElement(
      import_react_native4.TextInput,
      {
        style: styles4.input,
        keyboardType: "decimal-pad",
        placeholder: "42.50",
        value: amount,
        onChangeText: setAmount
      }
    ), /* @__PURE__ */ import_react4.default.createElement(import_react_native4.Text, { style: styles4.label }, "Description"), /* @__PURE__ */ import_react4.default.createElement(
      import_react_native4.TextInput,
      {
        style: styles4.input,
        placeholder: "bowling",
        value: description,
        onChangeText: setDescription
      }
    ), /* @__PURE__ */ import_react4.default.createElement(import_react_native4.Text, { style: styles4.label }, "Category"), /* @__PURE__ */ import_react4.default.createElement(import_react_native4.View, { style: styles4.chipsRow }, CATEGORIES.map((c) => /* @__PURE__ */ import_react4.default.createElement(
      import_react_native4.Pressable,
      {
        key: c,
        style: [styles4.chip, category === c && styles4.chipActive],
        onPress: () => setCategory(c)
      },
      /* @__PURE__ */ import_react4.default.createElement(import_react_native4.Text, { style: category === c ? styles4.chipTextActive : styles4.chipText }, c)
    ))), /* @__PURE__ */ import_react4.default.createElement(import_react_native4.Text, { style: styles4.hint }, "Tip: Save now, then tap the saved expense in the timeline to attach a receipt photo."), error && /* @__PURE__ */ import_react4.default.createElement(import_react_native4.Text, { style: styles4.error }, error), /* @__PURE__ */ import_react4.default.createElement(import_react_native4.View, { style: styles4.btnRow }, /* @__PURE__ */ import_react4.default.createElement(import_react_native4.Pressable, { style: styles4.cancelBtn, onPress: bridge.closeComponent }, /* @__PURE__ */ import_react4.default.createElement(import_react_native4.Text, { style: styles4.cancelBtnText }, "Cancel")), /* @__PURE__ */ import_react4.default.createElement(import_react_native4.Pressable, { style: styles4.saveBtn, onPress: save, disabled: saving }, saving ? /* @__PURE__ */ import_react4.default.createElement(import_react_native4.ActivityIndicator, { color: "#fff" }) : /* @__PURE__ */ import_react4.default.createElement(import_react_native4.Text, { style: styles4.saveBtnText }, "Save"))));
  }
  var styles4 = import_react_native4.StyleSheet.create({
    container: { padding: 16 },
    title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
    label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
    input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 16 },
    chipsRow: { flexDirection: "row", flexWrap: "wrap", marginTop: 4 },
    chip: { paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: "#ddd", borderRadius: 14, marginRight: 6, marginBottom: 6 },
    chipActive: { backgroundColor: "#2a7", borderColor: "#2a7" },
    chipText: { color: "#444", fontSize: 12 },
    chipTextActive: { color: "#fff", fontSize: 12, fontWeight: "600" },
    hint: { marginTop: 10, color: "#888", fontSize: 12 },
    error: { color: "#c22", marginTop: 8 },
    btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
    cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
    cancelBtnText: { fontWeight: "600", color: "#444" },
    saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
    saveBtnText: { color: "#fff", fontWeight: "600" }
  });

  // components/ExportSheet.tsx
  var import_react5 = __toESM(__require("react"), 1);
  var import_react_native5 = __require("react-native");
  function ExportSheet({ bridge }) {
    const [children, setChildren] = (0, import_react5.useState)([]);
    const [childId, setChildId] = (0, import_react5.useState)("");
    const [fromDate, setFromDate] = (0, import_react5.useState)(() => {
      const d = /* @__PURE__ */ new Date();
      d.setMonth(d.getMonth() - 1);
      return d.toISOString().slice(0, 10);
    });
    const [toDate, setToDate] = (0, import_react5.useState)((/* @__PURE__ */ new Date()).toISOString().slice(0, 10));
    const [format, setFormat] = (0, import_react5.useState)("pdf");
    const [status, setStatus] = (0, import_react5.useState)(null);
    const [busy, setBusy] = (0, import_react5.useState)(false);
    (0, import_react5.useEffect)(() => {
      bridge.callPluginApi("/api/plugins/custody/children", "GET", null).then((list) => {
        const rows = list;
        setChildren(rows);
        if (rows[0]) setChildId(rows[0].id);
      });
    }, [bridge]);
    const doExport = () => __async(this, null, function* () {
      if (!childId) return;
      setBusy(true);
      setStatus(null);
      try {
        const from = `${fromDate}T00:00:00`;
        const to = `${toDate}T23:59:59`;
        yield bridge.callPluginApi(
          `/api/plugins/custody/export?child_id=${childId}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&format=${format}`,
          "GET",
          null
        );
        setStatus(`Export generated. Re-open from the same URL to download.`);
      } catch (e) {
        setStatus(e.message || "Failed");
      } finally {
        setBusy(false);
      }
    });
    return /* @__PURE__ */ import_react5.default.createElement(import_react_native5.View, { style: styles5.container }, /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Text, { style: styles5.title }, "Export custody log"), /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Text, { style: styles5.label }, "Child"), /* @__PURE__ */ import_react5.default.createElement(import_react_native5.View, { style: styles5.row }, children.map((c) => /* @__PURE__ */ import_react5.default.createElement(
      import_react_native5.Pressable,
      {
        key: c.id,
        style: [styles5.chip, c.id === childId && styles5.chipActive],
        onPress: () => setChildId(c.id)
      },
      /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Text, { style: c.id === childId ? styles5.chipTextActive : styles5.chipText }, c.name)
    ))), /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Text, { style: styles5.label }, "From (YYYY-MM-DD)"), /* @__PURE__ */ import_react5.default.createElement(import_react_native5.TextInput, { style: styles5.input, value: fromDate, onChangeText: setFromDate }), /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Text, { style: styles5.label }, "To (YYYY-MM-DD)"), /* @__PURE__ */ import_react5.default.createElement(import_react_native5.TextInput, { style: styles5.input, value: toDate, onChangeText: setToDate }), /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Text, { style: styles5.label }, "Format"), /* @__PURE__ */ import_react5.default.createElement(import_react_native5.View, { style: styles5.row }, ["pdf", "csv"].map((f) => /* @__PURE__ */ import_react5.default.createElement(
      import_react_native5.Pressable,
      {
        key: f,
        style: [styles5.chip, format === f && styles5.chipActive],
        onPress: () => setFormat(f)
      },
      /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Text, { style: format === f ? styles5.chipTextActive : styles5.chipText }, f.toUpperCase())
    ))), status && /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Text, { style: styles5.status }, status), /* @__PURE__ */ import_react5.default.createElement(import_react_native5.View, { style: styles5.btnRow }, /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Pressable, { style: styles5.cancelBtn, onPress: bridge.closeComponent }, /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Text, { style: styles5.cancelBtnText }, "Close")), /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Pressable, { style: styles5.saveBtn, onPress: doExport, disabled: busy }, busy ? /* @__PURE__ */ import_react5.default.createElement(import_react_native5.ActivityIndicator, { color: "#fff" }) : /* @__PURE__ */ import_react5.default.createElement(import_react_native5.Text, { style: styles5.saveBtnText }, "Export"))));
  }
  var styles5 = import_react_native5.StyleSheet.create({
    container: { padding: 16 },
    title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
    label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
    row: { flexDirection: "row", flexWrap: "wrap" },
    chip: { paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: "#ddd", borderRadius: 14, marginRight: 6, marginBottom: 6 },
    chipActive: { backgroundColor: "#2a7", borderColor: "#2a7" },
    chipText: { color: "#444", fontSize: 12 },
    chipTextActive: { color: "#fff", fontSize: 12, fontWeight: "600" },
    input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 14 },
    status: { color: "#444", marginTop: 10 },
    btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
    cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
    cancelBtnText: { fontWeight: "600", color: "#444" },
    saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
    saveBtnText: { color: "#fff", fontWeight: "600" }
  });

  // components/ScheduleForm.tsx
  var import_react6 = __toESM(__require("react"), 1);
  var import_react_native6 = __require("react-native");
  var DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"];
  function ScheduleForm({ bridge, scheduleId }) {
    const [children, setChildren] = (0, import_react6.useState)([]);
    const [childId, setChildId] = (0, import_react6.useState)("");
    const [name, setName] = (0, import_react6.useState)("");
    const [startDate, setStartDate] = (0, import_react6.useState)((/* @__PURE__ */ new Date()).toISOString().slice(0, 10));
    const [intervalWeeks, setIntervalWeeks] = (0, import_react6.useState)("1");
    const [weekdaySet, setWeekdaySet] = (0, import_react6.useState)(/* @__PURE__ */ new Set([4]));
    const [pickupTime, setPickupTime] = (0, import_react6.useState)("17:00");
    const [dropoffTime, setDropoffTime] = (0, import_react6.useState)("19:00");
    const [pickupLocation, setPickupLocation] = (0, import_react6.useState)("");
    const [saving, setSaving] = (0, import_react6.useState)(false);
    const [error, setError] = (0, import_react6.useState)(null);
    const [loaded, setLoaded] = (0, import_react6.useState)(!scheduleId);
    (0, import_react6.useEffect)(() => {
      bridge.callPluginApi("/api/plugins/custody/children", "GET", null).then((list) => {
        const rows = list;
        setChildren(rows);
        if (rows[0] && !childId) setChildId(rows[0].id);
      });
    }, [bridge]);
    (0, import_react6.useEffect)(() => {
      if (!scheduleId) return;
      bridge.callPluginApi(
        "/api/plugins/custody/schedules",
        "GET",
        null
      ).then((list) => {
        const found = list.find((s) => s.id === scheduleId);
        if (found) {
          setChildId(found.child_id);
          setName(found.name);
          setStartDate(found.start_date);
          setIntervalWeeks(String(found.interval_weeks));
          setWeekdaySet(new Set(found.weekdays.split(",").map(Number)));
          setPickupTime(found.pickup_time);
          setDropoffTime(found.dropoff_time);
          setPickupLocation(found.pickup_location || "");
        }
      }).finally(() => setLoaded(true));
    }, [bridge, scheduleId]);
    const toggleDay = (i) => {
      const next = new Set(weekdaySet);
      next.has(i) ? next.delete(i) : next.add(i);
      setWeekdaySet(next);
    };
    const save = () => __async(this, null, function* () {
      if (!childId) {
        setError("Pick a child first");
        return;
      }
      if (weekdaySet.size === 0) {
        setError("Pick at least one weekday");
        return;
      }
      setSaving(true);
      setError(null);
      const payload = {
        child_id: childId,
        name: name.trim() || "Schedule",
        start_date: startDate,
        interval_weeks: Math.max(1, parseInt(intervalWeeks, 10) || 1),
        weekdays: Array.from(weekdaySet).sort().join(","),
        pickup_time: pickupTime,
        dropoff_time: dropoffTime,
        pickup_location: pickupLocation.trim() || null
      };
      try {
        if (scheduleId) {
          yield bridge.callPluginApi(
            `/api/plugins/custody/schedules/${scheduleId}`,
            "PATCH",
            payload
          );
        } else {
          yield bridge.callPluginApi("/api/plugins/custody/schedules", "POST", payload);
        }
        bridge.showToast("Saved");
        bridge.closeComponent();
      } catch (e) {
        setError(e.message || "Failed");
      } finally {
        setSaving(false);
      }
    });
    if (!loaded) return /* @__PURE__ */ import_react6.default.createElement(import_react_native6.ActivityIndicator, { style: { marginTop: 40 } });
    return /* @__PURE__ */ import_react6.default.createElement(import_react_native6.View, { style: styles6.container }, /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.title }, scheduleId ? "Edit schedule" : "New schedule"), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.label }, "Child"), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.View, { style: styles6.row }, children.map((c) => /* @__PURE__ */ import_react6.default.createElement(
      import_react_native6.Pressable,
      {
        key: c.id,
        style: [styles6.chip, c.id === childId && styles6.chipActive],
        onPress: () => setChildId(c.id)
      },
      /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: c.id === childId ? styles6.chipTextActive : styles6.chipText }, c.name)
    ))), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.label }, "Name"), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.TextInput, { style: styles6.input, value: name, onChangeText: setName, placeholder: "EOW Fri-Sun" }), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.label }, "Start date (YYYY-MM-DD)"), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.TextInput, { style: styles6.input, value: startDate, onChangeText: setStartDate }), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.label }, "Interval (weeks)"), /* @__PURE__ */ import_react6.default.createElement(
      import_react_native6.TextInput,
      {
        style: styles6.input,
        keyboardType: "numeric",
        value: intervalWeeks,
        onChangeText: setIntervalWeeks
      }
    ), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.label }, "Weekdays"), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.View, { style: styles6.row }, DAY_LABELS.map((lbl, i) => /* @__PURE__ */ import_react6.default.createElement(
      import_react_native6.Pressable,
      {
        key: i,
        style: [styles6.dayBtn, weekdaySet.has(i) && styles6.dayBtnOn],
        onPress: () => toggleDay(i)
      },
      /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: weekdaySet.has(i) ? styles6.dayTextOn : styles6.dayText }, lbl)
    ))), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.label }, "Pickup (HH:MM)"), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.TextInput, { style: styles6.input, value: pickupTime, onChangeText: setPickupTime }), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.label }, "Dropoff (HH:MM)"), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.TextInput, { style: styles6.input, value: dropoffTime, onChangeText: setDropoffTime }), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.label }, "Pickup location (optional)"), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.TextInput, { style: styles6.input, value: pickupLocation, onChangeText: setPickupLocation }), error && /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.error }, error), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.View, { style: styles6.btnRow }, /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Pressable, { style: styles6.cancelBtn, onPress: bridge.closeComponent }, /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.cancelBtnText }, "Cancel")), /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Pressable, { style: styles6.saveBtn, onPress: save, disabled: saving }, saving ? /* @__PURE__ */ import_react6.default.createElement(import_react_native6.ActivityIndicator, { color: "#fff" }) : /* @__PURE__ */ import_react6.default.createElement(import_react_native6.Text, { style: styles6.saveBtnText }, "Save"))));
  }
  var styles6 = import_react_native6.StyleSheet.create({
    container: { padding: 16 },
    title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
    label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
    row: { flexDirection: "row", flexWrap: "wrap" },
    input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 14 },
    chip: { paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: "#ddd", borderRadius: 14, marginRight: 6, marginBottom: 6 },
    chipActive: { backgroundColor: "#2a7", borderColor: "#2a7" },
    chipText: { color: "#444", fontSize: 12 },
    chipTextActive: { color: "#fff", fontSize: 12, fontWeight: "600" },
    dayBtn: { width: 36, height: 36, borderRadius: 18, borderWidth: 1, borderColor: "#ddd", alignItems: "center", justifyContent: "center", marginRight: 6 },
    dayBtnOn: { backgroundColor: "#2a7", borderColor: "#2a7" },
    dayText: { color: "#444" },
    dayTextOn: { color: "#fff", fontWeight: "600" },
    error: { color: "#c22", marginTop: 8 },
    btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
    cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
    cancelBtnText: { fontWeight: "600", color: "#444" },
    saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
    saveBtnText: { color: "#fff", fontWeight: "600" }
  });

  // components/ScheduleListScreen.tsx
  var import_react7 = __toESM(__require("react"), 1);
  var import_react_native7 = __require("react-native");
  function ScheduleListScreen({ bridge }) {
    const [rows, setRows] = (0, import_react7.useState)([]);
    const [loading, setLoading] = (0, import_react7.useState)(true);
    const load = () => __async(this, null, function* () {
      setLoading(true);
      const data = yield bridge.callPluginApi(
        "/api/plugins/custody/schedules",
        "GET",
        null
      );
      setRows(data);
      setLoading(false);
    });
    (0, import_react7.useEffect)(() => {
      load();
    }, []);
    if (loading) return /* @__PURE__ */ import_react7.default.createElement(import_react_native7.ActivityIndicator, { style: { marginTop: 40 } });
    return /* @__PURE__ */ import_react7.default.createElement(import_react_native7.View, { style: styles7.container }, /* @__PURE__ */ import_react7.default.createElement(import_react_native7.Text, { style: styles7.title }, "Schedules"), /* @__PURE__ */ import_react7.default.createElement(
      import_react_native7.FlatList,
      {
        data: rows,
        keyExtractor: (r) => r.id,
        renderItem: ({ item }) => /* @__PURE__ */ import_react7.default.createElement(
          import_react_native7.Pressable,
          {
            style: styles7.row,
            onPress: () => {
              var _a;
              return (_a = bridge.openComponent) == null ? void 0 : _a.call(bridge, "ScheduleForm", { scheduleId: item.id });
            }
          },
          /* @__PURE__ */ import_react7.default.createElement(import_react_native7.Text, { style: styles7.name }, item.name),
          /* @__PURE__ */ import_react7.default.createElement(import_react_native7.Text, { style: styles7.sub }, "Every ", item.interval_weeks, "w \xB7 days ", item.weekdays, " \xB7", " ", item.pickup_time, "\u2192", item.dropoff_time)
        ),
        ListEmptyComponent: /* @__PURE__ */ import_react7.default.createElement(import_react_native7.Text, { style: styles7.empty }, "No schedules yet.")
      }
    ), /* @__PURE__ */ import_react7.default.createElement(
      import_react_native7.Pressable,
      {
        style: styles7.primary,
        onPress: () => {
          var _a;
          return (_a = bridge.openComponent) == null ? void 0 : _a.call(bridge, "ScheduleForm");
        }
      },
      /* @__PURE__ */ import_react7.default.createElement(import_react_native7.Text, { style: styles7.primaryText }, "+ Add schedule")
    ));
  }
  var styles7 = import_react_native7.StyleSheet.create({
    container: { padding: 16 },
    title: { fontSize: 18, fontWeight: "700", marginBottom: 10 },
    row: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#f0f0f0" },
    name: { fontSize: 15, fontWeight: "600" },
    sub: { fontSize: 12, color: "#666" },
    empty: { color: "#888", padding: 20, textAlign: "center" },
    primary: { backgroundColor: "#2a7", padding: 12, borderRadius: 6, alignItems: "center", marginTop: 12 },
    primaryText: { color: "#fff", fontWeight: "600" }
  });

  // components/TextCaptureForm.tsx
  var import_react8 = __toESM(__require("react"), 1);
  var import_react_native8 = __require("react-native");
  function TextCaptureForm({ bridge, childId }) {
    const [note, setNote] = (0, import_react8.useState)("");
    const [saving, setSaving] = (0, import_react8.useState)(false);
    const [error, setError] = (0, import_react8.useState)(null);
    const save = () => __async(this, null, function* () {
      setSaving(true);
      setError(null);
      try {
        yield bridge.callPluginApi("/api/plugins/custody/events", "POST", {
          child_id: childId,
          type: "text_screenshot",
          occurred_at: (/* @__PURE__ */ new Date()).toISOString(),
          notes: note.trim() || null
        });
        bridge.showToast("Text event logged \u2014 attach screenshots from timeline");
        bridge.closeComponent();
      } catch (e) {
        setError(e.message || "Failed to save");
      } finally {
        setSaving(false);
      }
    });
    return /* @__PURE__ */ import_react8.default.createElement(import_react_native8.View, { style: styles8.container }, /* @__PURE__ */ import_react8.default.createElement(import_react_native8.Text, { style: styles8.title }, "Log text from other parent"), /* @__PURE__ */ import_react8.default.createElement(import_react_native8.Text, { style: styles8.hint }, "Save this event, then tap it in the timeline to attach a screenshot."), /* @__PURE__ */ import_react8.default.createElement(import_react_native8.Text, { style: styles8.label }, "Note (optional)"), /* @__PURE__ */ import_react8.default.createElement(
      import_react_native8.TextInput,
      {
        style: [styles8.input, { height: 80 }],
        multiline: true,
        placeholder: "e.g. refused my Sunday pickup window",
        value: note,
        onChangeText: setNote
      }
    ), error && /* @__PURE__ */ import_react8.default.createElement(import_react_native8.Text, { style: styles8.error }, error), /* @__PURE__ */ import_react8.default.createElement(import_react_native8.View, { style: styles8.btnRow }, /* @__PURE__ */ import_react8.default.createElement(import_react_native8.Pressable, { style: styles8.cancelBtn, onPress: bridge.closeComponent }, /* @__PURE__ */ import_react8.default.createElement(import_react_native8.Text, { style: styles8.cancelBtnText }, "Cancel")), /* @__PURE__ */ import_react8.default.createElement(import_react_native8.Pressable, { style: styles8.saveBtn, onPress: save, disabled: saving }, saving ? /* @__PURE__ */ import_react8.default.createElement(import_react_native8.ActivityIndicator, { color: "#fff" }) : /* @__PURE__ */ import_react8.default.createElement(import_react_native8.Text, { style: styles8.saveBtnText }, "Save"))));
  }
  var styles8 = import_react_native8.StyleSheet.create({
    container: { padding: 16 },
    title: { fontSize: 18, fontWeight: "700", marginBottom: 4 },
    hint: { color: "#888", fontSize: 12, marginBottom: 14 },
    label: { fontSize: 12, color: "#666", marginTop: 10, marginBottom: 4, letterSpacing: 0.5, textTransform: "uppercase" },
    input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 6, padding: 10, fontSize: 16, textAlignVertical: "top" },
    error: { color: "#c22", marginTop: 8 },
    btnRow: { flexDirection: "row", marginTop: 16, gap: 10 },
    cancelBtn: { flex: 1, padding: 12, borderWidth: 1, borderColor: "#ccc", borderRadius: 6, alignItems: "center" },
    cancelBtnText: { fontWeight: "600", color: "#444" },
    saveBtn: { flex: 1, padding: 12, backgroundColor: "#2a7", borderRadius: 6, alignItems: "center" },
    saveBtnText: { color: "#fff", fontWeight: "600" }
  });

  // components/index.ts
  globalThis.JainPlugins = globalThis.JainPlugins || {};
  globalThis.JainPlugins.custody = {
    CustodyHome,
    ExpenseForm,
    TextCaptureForm,
    EventForm,
    ScheduleForm,
    ScheduleListScreen,
    ChildrenScreen,
    ExportSheet
  };
})();
