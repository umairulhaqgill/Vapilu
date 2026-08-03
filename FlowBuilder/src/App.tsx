import { useState } from "react";
import "./App.css";
import TenantList from "./pages/TenantList";
import FlowList from "./pages/FlowList";
import FlowEditor from "./pages/FlowEditor";
import TenantSettings from "./pages/TenantSettings";
import CallTest from "./pages/CallTest";

type FlowsView =
  | { screen: "tenants" }
  | { screen: "flows"; tenantId: string }
  | { screen: "editor"; tenantId: string; flowId: string }
  | { screen: "settings"; tenantId: string };

type Tab = "flows" | "call-test";

export default function App() {
  const [tab, setTab] = useState<Tab>("flows");
  const [flowsView, setFlowsView] = useState<FlowsView>({ screen: "tenants" });

  return (
    <div className="app">
      <header className="app-header">
        <span className="brand">Vapilu Flow Builder</span>
        <nav className="tab-nav">
          <button type="button" className={tab === "flows" ? "tab-active" : ""} onClick={() => setTab("flows")}>
            Flows
          </button>
          <button type="button" className={tab === "call-test" ? "tab-active" : ""} onClick={() => setTab("call-test")}>
            Call Test
          </button>
        </nav>
        <span className="dev-tag">developer tool - super-admin only, not for tenant login</span>
      </header>

      <main className="app-main">
        {tab === "flows" && (
          <>
            {flowsView.screen === "tenants" && (
              <TenantList onOpenTenant={(tenantId) => setFlowsView({ screen: "flows", tenantId })} />
            )}

            {flowsView.screen === "flows" && (
              <FlowList
                tenantId={flowsView.tenantId}
                onOpenFlow={(flowId) => setFlowsView({ screen: "editor", tenantId: flowsView.tenantId, flowId })}
                onOpenSettings={() => setFlowsView({ screen: "settings", tenantId: flowsView.tenantId })}
                onBack={() => setFlowsView({ screen: "tenants" })}
              />
            )}

            {flowsView.screen === "editor" && (
              <FlowEditor
                flowId={flowsView.flowId}
                onBack={() => setFlowsView({ screen: "flows", tenantId: flowsView.tenantId })}
              />
            )}

            {flowsView.screen === "settings" && (
              <TenantSettings
                tenantId={flowsView.tenantId}
                onBack={() => setFlowsView({ screen: "flows", tenantId: flowsView.tenantId })}
              />
            )}
          </>
        )}

        {tab === "call-test" && <CallTest />}
      </main>
    </div>
  );
}
