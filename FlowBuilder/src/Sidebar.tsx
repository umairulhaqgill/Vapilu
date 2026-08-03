import { useEffect, useState } from "react";
import { Building2, LayoutDashboard, ListTree, LogOut, PhoneCall, Settings as SettingsIcon } from "lucide-react";
import { api, ApiError } from "./api";
import ThemeToggle from "./ThemeToggle";

export type TenantSection = "flows" | "settings";

interface Props {
  activeTenantId: string | null;
  activeSection: TenantSection | null;
  dashboardActive: boolean;
  callTestActive: boolean;
  onSelectDashboard: () => void;
  onSelectSection: (tenantId: string, section: TenantSection) => void;
  onSelectCallTest: () => void;
  onLogout: () => void;
}

export default function Sidebar({
  activeTenantId,
  activeSection,
  dashboardActive,
  callTestActive,
  onSelectDashboard,
  onSelectSection,
  onSelectCallTest,
  onLogout,
}: Props) {
  const [tenantIds, setTenantIds] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listTenants()
      .then((r) => setTenantIds(r.tenant_ids))
      .catch((e) => setError(e instanceof ApiError ? String(e.message) : "Failed to load tenants"));
  }, []);

  return (
    <nav className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-brand-mark">V</span>
        <span>Vapilu</span>
      </div>

      <div className="sidebar-section">
        <button
          type="button"
          className={`sidebar-item${dashboardActive ? " sidebar-item-active" : ""}`}
          onClick={onSelectDashboard}
        >
          <LayoutDashboard size={15} />
          Dashboard
        </button>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-label">Tenants</div>

        {error && <p className="sidebar-error">{error}</p>}
        {!tenantIds && !error && <p className="sidebar-muted">Loading...</p>}
        {tenantIds?.length === 0 && <p className="sidebar-muted">No tenants found.</p>}

        {tenantIds?.map((id) => {
          const isActiveTenant = id === activeTenantId;
          return (
            <div key={id} className="sidebar-tenant">
              <button
                type="button"
                className={`sidebar-item sidebar-tenant-name${isActiveTenant ? " sidebar-item-active" : ""}`}
                onClick={() => onSelectSection(id, "flows")}
              >
                <Building2 size={15} />
                <span className="sidebar-tenant-name-text">{id}</span>
              </button>
              {isActiveTenant && (
                <div className="sidebar-subnav">
                  <button
                    type="button"
                    className={`sidebar-subitem${activeSection === "flows" ? " sidebar-subitem-active" : ""}`}
                    onClick={() => onSelectSection(id, "flows")}
                  >
                    <ListTree size={13} />
                    Flows
                  </button>
                  <button
                    type="button"
                    className={`sidebar-subitem${activeSection === "settings" ? " sidebar-subitem-active" : ""}`}
                    onClick={() => onSelectSection(id, "settings")}
                  >
                    <SettingsIcon size={13} />
                    Settings
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="sidebar-section sidebar-section-bottom">
        <button
          type="button"
          className={`sidebar-item${callTestActive ? " sidebar-item-active" : ""}`}
          onClick={onSelectCallTest}
        >
          <PhoneCall size={15} />
          Call Test
        </button>
      </div>

      <div className="sidebar-user">
        <div className="sidebar-user-avatar">A</div>
        <div className="sidebar-user-info">
          <div className="sidebar-user-name">Admin</div>
          <button type="button" className="sidebar-logout" onClick={onLogout}>
            <LogOut size={11} />
            Log out
          </button>
        </div>
      </div>

      <div className="sidebar-footer">
        <ThemeToggle />
        <span>developer tool - super-admin only</span>
      </div>
    </nav>
  );
}
