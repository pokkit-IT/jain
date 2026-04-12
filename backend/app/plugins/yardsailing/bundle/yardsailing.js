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
  var EMPTY = {
    title: "",
    description: "",
    address: "",
    start_date: "",
    end_date: "",
    start_time: "",
    end_time: ""
  };
  function SaleForm({ initialData, bridge }) {
    const [data, setData] = (0, import_react.useState)(__spreadValues(__spreadValues({}, EMPTY), initialData));
    const [submitting, setSubmitting] = (0, import_react.useState)(false);
    const [error, setError] = (0, import_react.useState)(null);
    const [success, setSuccess] = (0, import_react.useState)(null);
    const set = (key, value) => setData((d) => __spreadProps(__spreadValues({}, d), { [key]: value }));
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
      import_react_native.TextInput,
      {
        style: styles.input,
        value: data.start_date,
        onChangeText: (v) => set("start_date", v),
        placeholder: "2026-04-11"
      }
    )), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.half }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "End Date"), /* @__PURE__ */ import_react.default.createElement(
      import_react_native.TextInput,
      {
        style: styles.input,
        value: data.end_date,
        onChangeText: (v) => set("end_date", v),
        placeholder: "2026-04-11"
      }
    ))), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.row }, /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.half }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "Start Time *"), /* @__PURE__ */ import_react.default.createElement(
      import_react_native.TextInput,
      {
        style: styles.input,
        value: data.start_time,
        onChangeText: (v) => set("start_time", v),
        placeholder: "08:00"
      }
    )), /* @__PURE__ */ import_react.default.createElement(import_react_native.View, { style: styles.half }, /* @__PURE__ */ import_react.default.createElement(import_react_native.Text, { style: styles.label }, "End Time *"), /* @__PURE__ */ import_react.default.createElement(
      import_react_native.TextInput,
      {
        style: styles.input,
        value: data.end_time,
        onChangeText: (v) => set("end_time", v),
        placeholder: "14:00"
      }
    ))), /* @__PURE__ */ import_react.default.createElement(
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
    successText: { color: "#065f46", fontSize: 14, fontWeight: "500" }
  });

  // components/index.ts
  globalThis.JainPlugins = globalThis.JainPlugins || {};
  globalThis.JainPlugins.yardsailing = {
    SaleForm
  };
})();
