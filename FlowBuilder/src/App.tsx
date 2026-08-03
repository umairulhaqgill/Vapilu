import { useState } from "react";
import "./App.css";
import Sidebar, { type TenantSection } from "./Sidebar";
import Breadcrumb, { type Crumb } from "./Breadcrumb";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import FlowList from "./pages/FlowList";
import FlowEditor from "./pages/FlowEditor";
import TenantSettings from "./pages/TenantSettings";
import CallTest from "./pages/CallTest";

type View =
  | { screen: "dashboard" }
  | { screen: "flows"; tenantId: string }
  | { screen: "editor"; tenantId: string; flowId: string }
  | { screen: "settings"; tenantId: string }
  | { screen: "call-test" };

const AUTH_KEY = "vapilu-dummy-auth";

export default function App() {
  // Dummy auth only - no credentials are checked and nothing is sent
  // anywhere. See Login.tsx / CLAUDE.md's "Known gaps that matter": real
  // per-user auth has to land server-side before any login screen here
  // could be real.
  const [authed, setAuthed] = useState(() => localStorage.getItem(AUTH_KEY) === "1");
  const [authScreen, setAuthScreen] = useState<"login" | "signup">("login");
  const [view, setView] = useState<View>({ screen: "dashboard" });

  const login = () => {
    localStorage.setItem(AUTH_KEY, "1");
    setAuthed(true);
  };
  const logout = () => {
    localStorage.removeItem(AUTH_KEY);
    setAuthed(false);
    setView({ screen: "dashboard" });
  };

  if (!authed) {
    return authScreen === "login" ? (
      <Login onLogin={login} onGoToSignup={() => setAuthScreen("signup")} />
    ) : (
      <Signup onSignup={login} onGoToLogin={() => setAuthScreen("login")} />
    );
  }

  const goDashboard = () => setView({ screen: "dashboard" });
  const goFlows = (tenantId: string) => setView({ screen: "flows", tenantId });
  const goSettings = (tenantId: string) => setView({ screen: "settings", tenantId });
  const goCallTest = () => setView({ screen: "call-test" });

  const activeTenantId = "tenantId" in view ? view.tenantId : null;
  const activeSection: TenantSection | null =
    view.screen === "flows" || view.screen === "editor" ? "flows" : view.screen === "settings" ? "settings" : null;

  let crumbs: Crumb[] = [];
  if (view.screen === "dashboard") {
    crumbs = [{ label: "Dashboard" }];
  } else if (view.screen === "flows") {
    crumbs = [{ label: view.tenantId }, { label: "Flows" }];
  } else if (view.screen === "editor") {
    crumbs = [
      { label: view.tenantId, onClick: () => goFlows(view.tenantId) },
      { label: "Flows", onClick: () => goFlows(view.tenantId) },
      { label: view.flowId },
    ];
  } else if (view.screen === "settings") {
    crumbs = [{ label: view.tenantId, onClick: () => goFlows(view.tenantId) }, { label: "Settings" }];
  } else if (view.screen === "call-test") {
    crumbs = [{ label: "Call Test" }];
  }

  return (
    <div className="app-shell">
      <Sidebar
        activeTenantId={activeTenantId}
        activeSection={activeSection}
        dashboardActive={view.screen === "dashboard"}
        callTestActive={view.screen === "call-test"}
        onSelectDashboard={goDashboard}
        onSelectSection={(tenantId, section) => (section === "flows" ? goFlows(tenantId) : goSettings(tenantId))}
        onSelectCallTest={goCallTest}
        onLogout={logout}
      />

      <div className="content">
        {crumbs.length > 0 && (
          <div className="content-topbar">
            <Breadcrumb items={crumbs} />
          </div>
        )}

        <div className="content-page">
          {view.screen === "dashboard" && <Dashboard />}

          {view.screen === "flows" && (
            <FlowList
              tenantId={view.tenantId}
              onOpenFlow={(flowId) => setView({ screen: "editor", tenantId: view.tenantId, flowId })}
            />
          )}

          {view.screen === "editor" && <FlowEditor flowId={view.flowId} />}

          {view.screen === "settings" && <TenantSettings tenantId={view.tenantId} />}

          {view.screen === "call-test" && <CallTest />}
        </div>
      </div>
    </div>
  );
}
