import { useState } from "react";
import "./App.css";
import TenantList from "./pages/TenantList";
import FlowList from "./pages/FlowList";
import FlowEditor from "./pages/FlowEditor";

type View =
  | { screen: "tenants" }
  | { screen: "flows"; tenantId: string }
  | { screen: "editor"; tenantId: string; flowId: string };

export default function App() {
  const [view, setView] = useState<View>({ screen: "tenants" });

  return (
    <div className="app">
      <header className="app-header">
        <span className="brand">Vapilu Flow Builder</span>
        <span className="dev-tag">developer tool - super-admin only, not for tenant login</span>
      </header>

      <main className="app-main">
        {view.screen === "tenants" && (
          <TenantList onOpenTenant={(tenantId) => setView({ screen: "flows", tenantId })} />
        )}

        {view.screen === "flows" && (
          <FlowList
            tenantId={view.tenantId}
            onOpenFlow={(flowId) => setView({ screen: "editor", tenantId: view.tenantId, flowId })}
            onBack={() => setView({ screen: "tenants" })}
          />
        )}

        {view.screen === "editor" && (
          <FlowEditor
            flowId={view.flowId}
            onBack={() => setView({ screen: "flows", tenantId: view.tenantId })}
          />
        )}
      </main>
    </div>
  );
}
