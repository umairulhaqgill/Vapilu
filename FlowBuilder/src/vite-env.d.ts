/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TENANT_SERVICE_URL?: string;
  readonly VITE_TENANT_SERVICE_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
