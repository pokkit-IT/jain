import { SaleForm } from "./SaleForm";
import { YardsailingHome } from "./YardsailingHome";
import { YardsailingMapLayer } from "./YardsailingMapLayer";

declare const globalThis: {
  JainPlugins?: Record<string, Record<string, unknown>>;
};

globalThis.JainPlugins = globalThis.JainPlugins || {};
globalThis.JainPlugins.yardsailing = {
  SaleForm,
  YardsailingHome,
  YardsailingMapLayer,
};

export { SaleForm, YardsailingHome, YardsailingMapLayer };
