import { useEffect, useState } from "react";
import { api, ApiError } from "../api";

interface Props {
  onOpenTenant: (tenantId: string) => void;
}

export default function TenantList({ onOpenTenant }: Props) {
  const [tenantIds, setTenantIds] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listTenants()
      .then((r) => setTenantIds(r.tenant_ids))
      .catch((e) => setError(e instanceof ApiError ? String(e.message) : "Failed to load tenants"));
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <h2>Tenants</h2>
      </div>

      {error && <p className="error">{error}</p>}
      {!tenantIds && !error && <p className="muted">Loading...</p>}

      {tenantIds && (
        <ul className="tenant-list">
          {tenantIds.map((id) => (
            <li key={id}>
              <button type="button" className="link-button" onClick={() => onOpenTenant(id)}>
                {id}
              </button>
            </li>
          ))}
          {tenantIds.length === 0 && <li className="muted">No tenants found.</li>}
        </ul>
      )}
    </div>
  );
}
