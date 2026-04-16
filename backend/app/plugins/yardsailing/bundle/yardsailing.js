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

  // components/SaleForm.tsx
  var import_react = __toESM(__require("react"), 1);
  var import_react_native = __require("react-native");
  var import_datetimepicker = __toESM(__require("@react-native-community/datetimepicker"), 1);
  function pad2(n) {
    return n < 10 ? `0${n}` : String(n);
  }
  function dateToIso(d) {
    return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  }
  function timeToHHMM(d) {
    return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
  }
  function nextWeekdayIso(target, from) {
    const d = from ? new Date(from) : /* @__PURE__ */ new Date();
    d.setHours(0, 0, 0, 0);
    const diff = (target - d.getDay() + 7) % 7;
    d.setDate(d.getDate() + diff);
    return dateToIso(d);
  }
  function parseIsoDate(iso) {
    if (iso) {
      const d = /* @__PURE__ */ new Date(iso + "T00:00:00");
      if (!isNaN(d.getTime())) return d;
    }
    return /* @__PURE__ */ new Date();
  }
  function parseHHMM(s) {
    const d = /* @__PURE__ */ new Date();
    d.setSeconds(0, 0);
    if (s && /^\d{1,2}:\d{2}$/.test(s)) {
      const [h, m] = s.split(":").map(Number);
      d.setHours(h, m);
    } else {
      d.setHours(9, 0);
    }
    return d;
  }
  var FALLBACK_TAGS = [
    "Furniture",
    "Toys",
    "Tools",
    "Baby Items",
    "Clothing",
    "Books",
    "Electronics",
    "Kitchen",
    "Sports",
    "Garden",
    "Holiday",
    "Art",
    "Free"
  ];
  function datesInRange(startIso, endIso) {
    if (!startIso) return [];
    const start = /* @__PURE__ */ new Date(startIso + "T00:00:00");
    if (isNaN(start.getTime())) return [];
    const end = endIso ? /* @__PURE__ */ new Date(endIso + "T00:00:00") : start;
    if (isNaN(end.getTime()) || end < start) return [startIso];
    const out = [];
    const cur = new Date(start);
    while (cur <= end) {
      out.push(cur.toISOString().slice(0, 10));
      cur.setDate(cur.getDate() + 1);
    }
    return out;
  }
  function makeEmpty() {
    const startIso = nextWeekdayIso(5);
    const endIso = nextWeekdayIso(0, parseIsoDate(startIso));
    return {
      title: "",
      description: "",
      address: "",
      start_date: startIso,
      end_date: endIso,
      start_time: "08:00",
      end_time: "17:00",
      tags: [],
      days: [],
      groups: []
    };
  }
  function groupAcceptsDates(g, startIso, endIso) {
    if (!g.start_date || !g.end_date) return true;
    const effEnd = endIso || startIso;
    return g.start_date <= startIso && effEnd <= g.end_date;
  }
  function SaleForm({ initialData, bridge }) {
    var _a, _b;
    const [data, setData] = (0, import_react.useState)(__spreadValues(__spreadValues({}, makeEmpty()), initialData));
    const [submitting, setSubmitting] = (0, import_react.useState)(false);
    const [error, setError] = (0, import_react.useState)(null);
    const [success, setSuccess] = (0, import_react.useState)(null);
    const [tagVocab, setTagVocab] = (0, import_react.useState)(FALLBACK_TAGS);
    const [perDayHours, setPerDayHours] = (0, import_react.useState)(
      ((_b = (_a = initialData == null ? void 0 : initialData.days) == null ? void 0 : _a.length) != null ? _b : 0) > 0
    );
    const [groupQuery, setGroupQuery] = (0, import_react.useState)("");
    const [groupResults, setGroupResults] = (0, import_react.useState)([]);
    const [groupSearching, setGroupSearching] = (0, import_react.useState)(false);
    const [showCreateGroup, setShowCreateGroup] = (0, import_react.useState)(false);
    const [newGroup, setNewGroup] = (0, import_react.useState)({ name: "", description: "", start_date: "", end_date: "" });
    const [creatingGroup, setCreatingGroup] = (0, import_react.useState)(false);
    (0, import_react.useEffect)(() => {
      bridge.callPluginApi("/api/plugins/yardsailing/tags", "GET", null).then((res) => {
        const tags = res == null ? void 0 : res.tags;
        if (Array.isArray(tags) && tags.length > 0) setTagVocab(tags);
      }).catch(() => {
      });
    }, [bridge]);
    (0, import_react.useEffect)(() => {
      const q = groupQuery.trim();
      const handle = setTimeout(() => __async(this, null, function* () {
        setGroupSearching(true);
        try {
          const path = q ? `/api/plugins/yardsailing/groups?q=${encodeURIComponent(q)}` : "/api/plugins/yardsailing/groups";
          const res = yield bridge.callPluginApi(path, "GET", null);
          if (Array.isArray(res)) setGroupResults(res);
        } catch (e) {
          setGroupResults([]);
        } finally {
          setGroupSearching(false);
        }
      }), 250);
      return () => clearTimeout(handle);
    }, [groupQuery, bridge]);
    const addGroup = (g) => {
      setData((d) => {
        if (d.groups.some((x) => x.id === g.id)) return d;
        return __spreadProps(__spreadValues({}, d), { groups: [...d.groups, g] });
      });
      setGroupQuery("");
    };
    const removeGroup = (id) => {
      setData((d) => __spreadProps(__spreadValues({}, d), { groups: d.groups.filter((g) => g.id !== id) }));
    };
    const createAndAddGroup = () => __async(this, null, function* () {
      const name = newGroup.name.trim();
      if (!name) return;
      const body = { name };
      if (newGroup.description.trim()) body.description = newGroup.description.trim();
      if (newGroup.start_date && newGroup.end_date) {
        body.start_date = newGroup.start_date;
        body.end_date = newGroup.end_date;
      }
      setCreatingGroup(true);
      try {
        const res = yield bridge.callPluginApi(
          "/api/plugins/yardsailing/groups",
          "POST",
          body
        );
        addGroup(res);
        setShowCreateGroup(false);
        setNewGroup({ name: "", description: "", start_date: "", end_date: "" });
      } catch (e) {
        bridge.showToast(e.message || "Failed to create group");
      } finally {
        setCreatingGroup(false);
      }
    });
    const set = (key, value) => setData((d) => __spreadProps(__spreadValues({}, d), { [key]: value }));
    const rangeDates = datesInRange(data.start_date, data.end_date);
    const multiDay = rangeDates.length > 1;
    const [picker, setPicker] = (0, import_react.useState)(null);
    const applyPick = (target, selected) => {
      var _a2, _b2;
      if (target.kind === "date") {
        const iso = dateToIso(selected);
        set(target.field, iso);
        if (target.field === "start_date" && data.end_date && data.end_date < iso) {
          set("end_date", iso);
        }
      } else if ("dayDate" in target) {
        const existing = data.days.find((x) => x.day_date === target.dayDate);
        const st = target.which === "start" ? timeToHHMM(selected) : (_a2 = existing == null ? void 0 : existing.start_time) != null ? _a2 : data.start_time;
        const et = target.which === "end" ? timeToHHMM(selected) : (_b2 = existing == null ? void 0 : existing.end_time) != null ? _b2 : data.end_time;
        setDayHours(target.dayDate, st, et);
      } else {
        set(target.field, timeToHHMM(selected));
      }
    };
    const onPickerChange = (event, selected) => {
      console.log("[SaleForm] picker onChange", {
        type: event == null ? void 0 : event.type,
        selected: selected == null ? void 0 : selected.toISOString(),
        target: picker
      });
      const target = picker;
      if (!target) return;
      if (import_react_native.Platform.OS === "android") {
        setPicker(null);
        if ((event == null ? void 0 : event.type) === "dismissed" || !selected) return;
        applyPick(target, selected);
        return;
      }
      if (selected) applyPick(target, selected);
    };
    const setDayHours = (day, startT, endT) => {
      setData((d) => {
        const others = d.days.filter((x) => x.day_date !== day);
        const isDefault = startT === d.start_time && endT === d.end_time;
        const next = isDefault ? others : [...others, { day_date: day, start_time: startT, end_time: endT }];
        return __spreadProps(__spreadValues({}, d), { days: next });
      });
    };
    const toggleTag = (tag) => {
      setData((d) => __spreadProps(__spreadValues({}, d), {
        tags: d.tags.includes(tag) ? d.tags.filter((t) => t !== tag) : [...d.tags, tag]
      }));
    };
    const submit = () => __async(this, null, function* () {
      console.log("[SaleForm] submit pressed, data =", data);
      setError(null);
      setSuccess(null);
      const missing = [];
      if (!data.title) missing.push("title");
      if (!data.address) missing.push("address");
      if (!data.start_date) missing.push("start date");
      if (!data.start_time) missing.push("start time");
      if (!data.end_time) missing.push("end time");
      if (missing.length > 0) {
        const msg = `Missing required: ${missing.join(", ")}`;
        console.log("[SaleForm] validation failed:", msg);
        setError(msg);
        return;
      }
      setSubmitting(true);
      try {
        console.log("[SaleForm] calling bridge.callPluginApi");
        const result = yield bridge.callPluginApi("/api/plugins/yardsailing/sales", "POST", data);
        console.log("[SaleForm] bridge returned:", result);
        const newSaleId = result == null ? void 0 : result.id;
        if (newSaleId && data.groups.length > 0) {
          try {
            yield bridge.callPluginApi(
              `/api/plugins/yardsailing/sales/${newSaleId}/groups`,
              "POST",
              { group_ids: data.groups.map((g) => g.id) }
            );
          } catch (e) {
            bridge.showToast(
              "Sale created, but couldn't attach groups: " + (e.message || "unknown error")
            );
          }
        }
        setSuccess("Yard sale created!");
        bridge.showToast("Yard sale created!");
        setTimeout(() => bridge.closeComponent(), 800);
      } catch (e) {
        const msg = e.message || "Failed to create sale";
        console.log("[SaleForm] bridge error:", msg, e);
        setError(msg);
      } finally {
        setSubmitting(false);
      }
    });
    return /* @__PURE__ */ import_react.default.createElement(import_react_native.ScrollView, { style: styles.container }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.header }, "Create Yard Sale"), error ? /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.errorBox }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.errorText }, error)) : null, success ? /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.successBox }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.successText }, success)) : null, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "Title *"), /* @__PURE__ */ import_react.default.createElement(
      import_react_native.TextInput,
      {
        style: styles.input,
        value: data.title,
        onChangeText: (v) => set("title", v),
        placeholder: "Big Saturday Sale"
      }
    ), /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "Address *"), /* @__PURE__ */ import_react.default.createElement(
      import_react_native.TextInput,
      {
        style: styles.input,
        value: data.address,
        onChangeText: (v) => set("address", v),
        placeholder: "123 Main St"
      }
    ), /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "Description"), /* @__PURE__ */ import_react.default.createElement(
      import_react_native.TextInput,
      {
        style: [styles.input, styles.multiline],
        value: data.description,
        onChangeText: (v) => set("description", v),
        placeholder: "What you're selling...",
        multiline: true
      }
    ), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.row }, /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.half }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "Start Date *"), /* @__PURE__ */ import_react.default.createElement(
      import_react_native.Pressable,
      {
        style: styles.pickerField,
        onPress: () => setPicker({ kind: "date", field: "start_date" })
      },
      /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: data.start_date ? styles.pickerText : styles.pickerPlaceholder }, data.start_date || "Select date")
    )), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.half }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "End Date"), /* @__PURE__ */ import_react.default.createElement(
      import_react_native.Pressable,
      {
        style: styles.pickerField,
        onPress: () => setPicker({ kind: "date", field: "end_date" })
      },
      /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: data.end_date ? styles.pickerText : styles.pickerPlaceholder }, data.end_date || "Optional")
    ))), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.row }, /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.half }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, multiDay ? "Default Start Time *" : "Start Time *"), /* @__PURE__ */ import_react.default.createElement(
      import_react_native.Pressable,
      {
        style: styles.pickerField,
        onPress: () => setPicker({ kind: "time", field: "start_time" })
      },
      /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: data.start_time ? styles.pickerText : styles.pickerPlaceholder }, data.start_time || "Select time")
    )), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.half }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, multiDay ? "Default End Time *" : "End Time *"), /* @__PURE__ */ import_react.default.createElement(
      import_react_native.Pressable,
      {
        style: styles.pickerField,
        onPress: () => setPicker({ kind: "time", field: "end_time" })
      },
      /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: data.end_time ? styles.pickerText : styles.pickerPlaceholder }, data.end_time || "Select time")
    ))), multiDay ? /* @__PURE__ */ import_react.default.createElement(
      import_react_native.TouchableOpacity,
      {
        style: styles.checkboxRow,
        onPress: () => {
          const next = !perDayHours;
          setPerDayHours(next);
          if (!next) setData((d) => __spreadProps(__spreadValues({}, d), { days: [] }));
        }
      },
      /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: [styles.checkbox, perDayHours && styles.checkboxOn] }, perDayHours ? /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.checkboxMark }, "\u2713") : null),
      /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.checkboxLabel }, "Times are different per day")
    ) : null, multiDay && perDayHours ? /* @__PURE__ */ import_react.default.createElement(import_react.default.Fragment, null, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.hint }, "Adjust any day if hours differ from the defaults above."), rangeDates.map((d) => {
      var _a2, _b2;
      const override = data.days.find((x) => x.day_date === d);
      const st = (_a2 = override == null ? void 0 : override.start_time) != null ? _a2 : data.start_time;
      const et = (_b2 = override == null ? void 0 : override.end_time) != null ? _b2 : data.end_time;
      return /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { key: d, style: styles.dayRow }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.dayDate }, d), /* @__PURE__ */ import_react.default.createElement(
        import_react_native.Pressable,
        {
          style: [styles.pickerField, styles.dayInput],
          onPress: () => setPicker({ kind: "time", dayDate: d, which: "start" })
        },
        /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.pickerText }, st)
      ), /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.dayDash }, "\u2013"), /* @__PURE__ */ import_react.default.createElement(
        import_react_native.Pressable,
        {
          style: [styles.pickerField, styles.dayInput],
          onPress: () => setPicker({ kind: "time", dayDate: d, which: "end" })
        },
        /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.pickerText }, et)
      ));
    })) : null, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "Tags"), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.tagRow }, tagVocab.map((tag) => {
      const active = data.tags.includes(tag);
      return /* @__PURE__ */ import_react.default.createElement(
        import_react_native.TouchableOpacity,
        {
          key: tag,
          onPress: () => toggleTag(tag),
          style: [styles.tagChip, active && styles.tagChipActive]
        },
        /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: [styles.tagText, active && styles.tagTextActive] }, tag)
      );
    })), /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "Groups"), /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.hint }, 'Optional. Attach this sale to events like "100 Mile Yard Sale".'), data.groups.length > 0 ? /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.tagRow }, data.groups.map((g) => {
      const ok = groupAcceptsDates(g, data.start_date, data.end_date);
      return /* @__PURE__ */ import_react.default.createElement(
        import_react_native.TouchableOpacity,
        {
          key: g.id,
          onPress: () => removeGroup(g.id),
          style: [
            styles.groupChip,
            ok ? styles.groupChipActive : styles.groupChipBad
          ]
        },
        /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.groupChipText }, g.name, " ", ok ? "\xD7" : "\u26A0")
      );
    })) : null, /* @__PURE__ */ import_react.default.createElement(
      import_react_native.TextInput,
      {
        style: styles.input,
        value: groupQuery,
        onChangeText: setGroupQuery,
        placeholder: "Find or create a group\u2026"
      }
    ), groupQuery.trim() !== "" ? /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.groupResults }, groupSearching ? /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.hint }, "Searching\u2026") : null, groupResults.filter((g) => !data.groups.some((s) => s.id === g.id)).map((g) => {
      const ok = groupAcceptsDates(g, data.start_date, data.end_date);
      return /* @__PURE__ */ import_react.default.createElement(
        import_react_native.TouchableOpacity,
        {
          key: g.id,
          onPress: () => ok && addGroup(g),
          disabled: !ok,
          style: [styles.groupRow, !ok && styles.groupRowDisabled]
        },
        /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.groupRowName }, g.name),
        g.start_date && g.end_date ? /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.groupRowDates }, g.start_date, " \u2013 ", g.end_date, !ok ? "  (doesn't fit sale dates)" : "") : null
      );
    }), !groupSearching && !groupResults.some(
      (g) => g.name.toLowerCase() === groupQuery.trim().toLowerCase()
    ) ? /* @__PURE__ */ import_react.default.createElement(
      import_react_native.TouchableOpacity,
      {
        style: styles.groupRow,
        onPress: () => {
          setNewGroup({
            name: groupQuery.trim(),
            description: "",
            start_date: "",
            end_date: ""
          });
          setShowCreateGroup(true);
        }
      },
      /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.groupCreateText }, '+ Create "', groupQuery.trim(), '"')
    ) : null) : null, /* @__PURE__ */ import_react.default.createElement(
      import_react_native.Modal,
      {
        transparent: true,
        animationType: "fade",
        visible: showCreateGroup,
        onRequestClose: () => setShowCreateGroup(false)
      },
      /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.modalBackdrop }, /* @__PURE__ */ import_react.default.createElement(
        import_react_native.Pressable,
        {
          style: import_react_native.StyleSheet.absoluteFill,
          onPress: () => setShowCreateGroup(false)
        }
      ), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.modalCard }, /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: { padding: 16 } }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.header }, "New group"), /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "Name *"), /* @__PURE__ */ import_react.default.createElement(
        import_react_native.TextInput,
        {
          style: styles.input,
          value: newGroup.name,
          onChangeText: (v) => setNewGroup((g) => __spreadProps(__spreadValues({}, g), { name: v })),
          placeholder: "e.g. 100 Mile Yard Sale"
        }
      ), /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "Description"), /* @__PURE__ */ import_react.default.createElement(
        import_react_native.TextInput,
        {
          style: styles.input,
          value: newGroup.description,
          onChangeText: (v) => setNewGroup((g) => __spreadProps(__spreadValues({}, g), { description: v })),
          placeholder: "Optional"
        }
      ), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.row }, /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.half }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "Start Date"), /* @__PURE__ */ import_react.default.createElement(
        import_react_native.TextInput,
        {
          style: styles.input,
          value: newGroup.start_date,
          onChangeText: (v) => setNewGroup((g) => __spreadProps(__spreadValues({}, g), { start_date: v })),
          placeholder: "YYYY-MM-DD"
        }
      )), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.half }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "End Date"), /* @__PURE__ */ import_react.default.createElement(
        import_react_native.TextInput,
        {
          style: styles.input,
          value: newGroup.end_date,
          onChangeText: (v) => setNewGroup((g) => __spreadProps(__spreadValues({}, g), { end_date: v })),
          placeholder: "YYYY-MM-DD"
        }
      ))), /* @__PURE__ */ import_react.default.createElement(
        import_react_native.TouchableOpacity,
        {
          style: [styles.button, creatingGroup && styles.buttonDisabled],
          onPress: createAndAddGroup,
          disabled: creatingGroup
        },
        /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.buttonText }, creatingGroup ? "Creating\u2026" : "Create group")
      ))))
    ), picker ? (() => {
      const pickerValue = (() => {
        var _a2, _b2;
        if (picker.kind === "date") {
          const iso = data[picker.field] || data.start_date;
          return parseIsoDate(iso);
        }
        if ("dayDate" in picker) {
          const row = data.days.find((x) => x.day_date === picker.dayDate);
          const hhmm = (picker.which === "start" ? (_a2 = row == null ? void 0 : row.start_time) != null ? _a2 : data.start_time : (_b2 = row == null ? void 0 : row.end_time) != null ? _b2 : data.end_time) || "09:00";
          return parseHHMM(hhmm);
        }
        return parseHHMM(data[picker.field] || "09:00");
      })();
      if (import_react_native.Platform.OS === "ios") {
        return /* @__PURE__ */ import_react.default.createElement(
          import_react_native.Modal,
          {
            transparent: true,
            animationType: "fade",
            visible: !!picker,
            onRequestClose: () => setPicker(null)
          },
          /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.modalBackdrop }, /* @__PURE__ */ import_react.default.createElement(
            import_react_native.Pressable,
            {
              style: import_react_native.StyleSheet.absoluteFill,
              onPress: () => setPicker(null)
            }
          ), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.modalCard }, /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.iosPickerHeader }, /* @__PURE__ */ import_react.default.createElement(import_react_native.TouchableOpacity, { onPress: () => setPicker(null) }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.iosPickerDone }, "Done"))), /* @__PURE__ */ import_react.default.createElement(
            import_datetimepicker.default,
            {
              mode: picker.kind,
              value: pickerValue,
              onChange: onPickerChange,
              is24Hour: false,
              display: picker.kind === "date" ? "inline" : "spinner",
              style: picker.kind === "date" ? { height: 360, alignSelf: "stretch" } : void 0
            }
          )))
        );
      }
      return /* @__PURE__ */ import_react.default.createElement(
        import_datetimepicker.default,
        {
          mode: picker.kind,
          value: pickerValue,
          onChange: onPickerChange,
          is24Hour: false,
          display: "default"
        }
      );
    })() : null, /* @__PURE__ */ import_react.default.createElement(
      import_react_native.TouchableOpacity,
      {
        style: [styles.button, submitting && styles.buttonDisabled],
        onPress: submit,
        disabled: submitting
      },
      /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.buttonText }, submitting ? "Creating..." : "Create Sale")
    ));
  }
  var styles = import_react_native.StyleSheet.create({
    container: { padding: 16, backgroundColor: "#fff" },
    header: { fontSize: 22, fontWeight: "600", marginBottom: 16 },
    label: { fontSize: 14, fontWeight: "500", marginTop: 12, marginBottom: 4 },
    input: {
      borderWidth: 1,
      borderColor: "#ccc",
      borderRadius: 8,
      padding: 10,
      fontSize: 16
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
      marginBottom: 40
    },
    buttonDisabled: { backgroundColor: "#94a3b8" },
    buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
    errorBox: {
      backgroundColor: "#fee2e2",
      borderWidth: 1,
      borderColor: "#fca5a5",
      borderRadius: 8,
      padding: 12,
      marginBottom: 12
    },
    errorText: { color: "#b91c1c", fontSize: 14, fontWeight: "500" },
    successBox: {
      backgroundColor: "#d1fae5",
      borderWidth: 1,
      borderColor: "#6ee7b7",
      borderRadius: 8,
      padding: 12,
      marginBottom: 12
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
      marginBottom: 6
    },
    tagChipActive: { backgroundColor: "#2563eb", borderColor: "#2563eb" },
    tagText: { fontSize: 13, color: "#334155", fontWeight: "600" },
    tagTextActive: { color: "#fff" },
    groupChip: {
      paddingHorizontal: 10,
      paddingVertical: 6,
      borderRadius: 14,
      borderWidth: 1,
      marginRight: 6,
      marginBottom: 6
    },
    groupChipActive: {
      backgroundColor: "#2563eb",
      borderColor: "#2563eb"
    },
    groupChipBad: {
      backgroundColor: "#fef3c7",
      borderColor: "#f59e0b"
    },
    groupChipText: { fontSize: 13, color: "#fff", fontWeight: "600" },
    groupResults: {
      marginTop: 4,
      borderWidth: 1,
      borderColor: "#e2e8f0",
      borderRadius: 8,
      backgroundColor: "#fff"
    },
    groupRow: {
      padding: 10,
      borderBottomWidth: 1,
      borderBottomColor: "#f1f5f9"
    },
    groupRowDisabled: { opacity: 0.5 },
    groupRowName: { fontSize: 14, color: "#0f172a", fontWeight: "600" },
    groupRowDates: { fontSize: 12, color: "#64748b", marginTop: 2 },
    groupCreateText: { fontSize: 14, color: "#2563eb", fontWeight: "600" },
    hint: { fontSize: 12, color: "#64748b", marginBottom: 8 },
    pickerField: {
      borderWidth: 1,
      borderColor: "#ccc",
      borderRadius: 8,
      paddingVertical: 12,
      paddingHorizontal: 10,
      backgroundColor: "#fff",
      justifyContent: "center"
    },
    pickerText: { fontSize: 16, color: "#0f172a" },
    pickerPlaceholder: { fontSize: 16, color: "#94a3b8" },
    iosPickerBox: {
      backgroundColor: "#f1f5f9",
      borderRadius: 10,
      marginTop: 8,
      marginBottom: 8,
      overflow: "hidden"
    },
    iosPickerHeader: {
      flexDirection: "row",
      justifyContent: "flex-end",
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderBottomWidth: 1,
      borderBottomColor: "#e2e8f0",
      backgroundColor: "#fff"
    },
    iosPickerDone: { color: "#2563eb", fontWeight: "700", fontSize: 15 },
    modalBackdrop: {
      flex: 1,
      backgroundColor: "rgba(0,0,0,0.5)",
      justifyContent: "center",
      paddingHorizontal: 16
    },
    checkboxRow: {
      flexDirection: "row",
      alignItems: "center",
      marginTop: 12,
      marginBottom: 4
    },
    checkbox: {
      width: 20,
      height: 20,
      borderRadius: 4,
      borderWidth: 1,
      borderColor: "#94a3b8",
      alignItems: "center",
      justifyContent: "center",
      marginRight: 8,
      backgroundColor: "#fff"
    },
    checkboxOn: {
      backgroundColor: "#2563eb",
      borderColor: "#2563eb"
    },
    checkboxMark: {
      color: "#fff",
      fontSize: 13,
      fontWeight: "700",
      lineHeight: 14
    },
    checkboxLabel: {
      fontSize: 14,
      color: "#0f172a"
    },
    modalCard: {
      backgroundColor: "#fff",
      borderRadius: 14,
      overflow: "hidden",
      paddingBottom: 8
    },
    dayRow: {
      flexDirection: "row",
      alignItems: "center",
      marginBottom: 6,
      gap: 6
    },
    dayDate: {
      width: 110,
      fontSize: 13,
      fontWeight: "600",
      color: "#334155"
    },
    dayInput: { flex: 1, paddingVertical: 6 },
    dayDash: { color: "#94a3b8", fontSize: 14 }
  });

  // components/YardsailingHome.tsx
  var import_react2 = __toESM(__require("react"), 1);
  var import_react_native2 = __require("react-native");
  function YardsailingHome({ bridge }) {
    const [sales, setSales] = (0, import_react2.useState)([]);
    const [loading, setLoading] = (0, import_react2.useState)(true);
    const [refreshing, setRefreshing] = (0, import_react2.useState)(false);
    const [error, setError] = (0, import_react2.useState)(null);
    const load = () => __async(this, null, function* () {
      setError(null);
      try {
        const res = yield bridge.callPluginApi(
          "/api/plugins/yardsailing/sales",
          "GET",
          null
        );
        setSales(Array.isArray(res) ? res : []);
      } catch (e) {
        setError(e.message || "Failed to load your sales.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    });
    (0, import_react2.useEffect)(() => {
      load();
    }, []);
    const onRefresh = () => {
      setRefreshing(true);
      load();
    };
    const confirmDelete = (sale) => {
      import_react_native2.Alert.alert(
        "Delete sale?",
        `"${sale.title}" will be removed. This can't be undone.`,
        [
          { text: "Cancel", style: "cancel" },
          {
            text: "Delete",
            style: "destructive",
            onPress: () => __async(this, null, function* () {
              try {
                yield bridge.callPluginApi(
                  `/api/plugins/yardsailing/sales/${sale.id}`,
                  "DELETE",
                  null
                );
                setSales((prev) => prev.filter((s) => s.id !== sale.id));
                bridge.showToast("Sale deleted.");
              } catch (e) {
                import_react_native2.Alert.alert("Delete failed", e.message);
              }
            })
          }
        ]
      );
    };
    const openCreate = () => {
      if (bridge.openComponent) {
        bridge.openComponent("SaleForm");
      } else {
        bridge.showToast("Ask Jain to create a yard sale from the Chat tab.");
      }
    };
    return /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: styles2.container }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: styles2.intro }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.heading }, "Yardsailing"), /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.blurb }, "Find yard sales on the Map, drop a pin on one you've spotted, or post your own."), /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Pressable, { style: styles2.createBtn, onPress: openCreate }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.createBtnText }, "+ Create yard sale"))), /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.sectionTitle }, "My sales"), loading ? /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: styles2.empty }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.ActivityIndicator, null)) : /* @__PURE__ */ import_react2.default.createElement(
      import_react_native2.FlatList,
      {
        data: sales,
        keyExtractor: (s) => s.id,
        refreshControl: /* @__PURE__ */ import_react2.default.createElement(import_react_native2.RefreshControl, { refreshing, onRefresh }),
        contentContainerStyle: sales.length === 0 ? styles2.empty : styles2.list,
        ListEmptyComponent: /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.emptyText }, error != null ? error : "No sales yet. Tap Create above."),
        renderItem: ({ item }) => {
          var _a;
          return /* @__PURE__ */ import_react2.default.createElement(import_react_native2.View, { style: styles2.card }, /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.title }, item.title), /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.address }, item.address), /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.meta }, (_a = item.start_date) != null ? _a : "", " ", item.start_time ? `\xB7 ${item.start_time}` : "", item.end_time ? `\u2013${item.end_time}` : ""), /* @__PURE__ */ import_react2.default.createElement(
            import_react_native2.Pressable,
            {
              style: styles2.deleteBtn,
              onPress: () => confirmDelete(item)
            },
            /* @__PURE__ */ import_react2.default.createElement(import_react_native2.Text, { style: styles2.deleteText }, "Delete")
          ));
        }
      }
    ));
  }
  var styles2 = import_react_native2.StyleSheet.create({
    container: { flex: 1, backgroundColor: "#f8fafc" },
    intro: {
      padding: 16,
      backgroundColor: "#fff",
      borderBottomWidth: 1,
      borderBottomColor: "#e2e8f0"
    },
    heading: { fontSize: 22, fontWeight: "700", marginBottom: 4 },
    blurb: { fontSize: 14, color: "#475569", marginBottom: 12 },
    createBtn: {
      backgroundColor: "#2563eb",
      paddingVertical: 12,
      borderRadius: 10,
      alignItems: "center"
    },
    createBtnText: { color: "#fff", fontSize: 15, fontWeight: "700" },
    sectionTitle: {
      fontSize: 13,
      fontWeight: "700",
      color: "#64748b",
      textTransform: "uppercase",
      paddingHorizontal: 16,
      paddingTop: 14,
      paddingBottom: 6
    },
    list: { padding: 12 },
    empty: {
      flexGrow: 1,
      alignItems: "center",
      justifyContent: "center",
      padding: 24
    },
    emptyText: { color: "#64748b", fontSize: 15, textAlign: "center" },
    card: {
      backgroundColor: "#fff",
      padding: 14,
      borderRadius: 10,
      borderWidth: 1,
      borderColor: "#e2e8f0",
      marginBottom: 10
    },
    title: { fontSize: 16, fontWeight: "700", marginBottom: 2 },
    address: { fontSize: 13, color: "#475569", marginBottom: 4 },
    meta: { fontSize: 12, color: "#64748b", marginBottom: 10 },
    deleteBtn: {
      alignSelf: "flex-start",
      backgroundColor: "#fee2e2",
      paddingVertical: 8,
      paddingHorizontal: 14,
      borderRadius: 8
    },
    deleteText: { color: "#b91c1c", fontWeight: "600" }
  });

  // components/index.ts
  globalThis.JainPlugins = globalThis.JainPlugins || {};
  globalThis.JainPlugins.yardsailing = {
    SaleForm,
    YardsailingHome
  };
})();
