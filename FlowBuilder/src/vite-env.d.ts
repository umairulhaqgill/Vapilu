/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TENANT_SERVICE_URL?: string;
  readonly VITE_TENANT_SERVICE_TOKEN?: string;
  readonly VITE_ORCHESTRATOR_URL?: string;
  readonly VITE_ORCHESTRATOR_TOKEN?: string;
  readonly VITE_CONNECTOR_GATEWAY_URL?: string;
  readonly VITE_CONNECTOR_GATEWAY_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
