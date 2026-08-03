interface StatTileProps {
  label: string;
  value: string;
  delta: string;
  deltaGood: boolean | null; // null = neutral, no direction judgement
}

function StatTile({ label, value, delta, deltaGood }: StatTileProps) {
  const deltaClass = deltaGood === null ? "stat-delta-neutral" : deltaGood ? "stat-delta-good" : "stat-delta-bad";
  return (
    <div className="stat-tile">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className={`stat-delta ${deltaClass}`}>{delta}</div>
    </div>
  );
}

// All figures below are placeholder/dummy data for the dashboard layout -
// nothing here is wired to a real metrics source yet.
const STATS: StatTileProps[] = [
  { label: "Active tenants", value: "3", delta: "+1 this month", deltaGood: true },
  { label: "Flows configured", value: "7", delta: "+2 this month", deltaGood: true },
  { label: "Calls this week", value: "128", delta: "+18% vs last week", deltaGood: true },
  { label: "Avg response latency", value: "1.4s", delta: "-0.3s vs last week", deltaGood: true },
  { label: "Barge-in rate", value: "22%", delta: "+3pp vs last week", deltaGood: null },
  { label: "Flows needing review", value: "1", delta: "unreachable node", deltaGood: false },
];

const ACTIVITY: { text: string; at: string }[] = [
  { text: "Flow \"book_repair\" updated - bike-shop", at: "2 hours ago" },
  { text: "Tenant settings saved - bike-shop", at: "5 hours ago" },
  { text: "New tenant added - school", at: "1 day ago" },
  { text: "Flow \"book_appointment\" created - dental-clinic", at: "3 days ago" },
];

export default function Dashboard() {
  return (
    <div className="page">
      <div className="page-header">
        <h2>Dashboard</h2>
      </div>
      <p className="muted" style={{ marginBottom: 20 }}>
        Placeholder overview - these figures are dummy data, not wired to a live metrics source yet.
      </p>

      <div className="stat-grid">
        {STATS.map((s) => (
          <StatTile key={s.label} {...s} />
        ))}
      </div>

      <div className="dashboard-panel">
        <div className="panel-section-header" style={{ margin: "0 0 8px" }}>
          <h4>Recent activity</h4>
        </div>
        <ul className="activity-list">
          {ACTIVITY.map((a, i) => (
            <li key={i} className="activity-item">
              <span>{a.text}</span>
              <span className="muted">{a.at}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
