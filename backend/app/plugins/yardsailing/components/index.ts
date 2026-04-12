import { SaleForm } from "./SaleForm";

// Register on global namespace for PluginHost to pick up
declare const globalThis: {
  JainPlugins?: Record<string, Record<string, unknown>>;
};

globalThis.JainPlugins = globalThis.JainPlugins || {};
globalThis.JainPlugins.yardsailing = {
  SaleForm,
};

export { SaleForm };
