export interface Bridge {
  callPluginApi: (path: string, method: string, body: unknown) => Promise<unknown>;
  closeComponent: () => void;
  showToast: (msg: string) => void;
  openComponent?: (name: string, props?: Record<string, unknown>) => void;
}

export interface WithBridge {
  bridge: Bridge;
}
