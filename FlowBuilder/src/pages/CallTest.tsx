import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { CallSession, type CallLogEntry, type CallStatus } from "../call/CallSession";

const DEFAULT_VAD_THRESHOLD = 1200;

export default function CallTest() {
  const [tenantIds, setTenantIds] = useState<string[] | null>(null);
  const [tenantId, setTenantId] = useState("");
  const [status, setStatus] = useState<CallStatus>("idle");
  const [logs, setLogs] = useState<CallLogEntry[]>([]);
  const [botPartial, setBotPartial] = useState("");
  const [level, setLevel] = useState(0);
  const [threshold, setThreshold] = useState(DEFAULT_VAD_THRESHOLD);

  const sessionRef = useRef<CallSession | null>(null);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api
      .listTenants()
      .then((r) => {
        setTenantIds(r.tenant_ids);
        if (r.tenant_ids.length > 0) setTenantId(r.tenant_ids[0]);
      })
      .catch((e) => {
        setLogs((prev) => [
          ...prev,
          { id: -1, kind: "error", at: Date.now(), text: e instanceof ApiError ? String(e.message) : "Failed to load tenants" },
        ]);
      });
  }, []);

  useEffect(() => {
    // End the call if the user navigates away mid-call rather than
    // leaving the mic and WebSocket open in the background.
    return () => {
      sessionRef.current?.end();
    };
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, botPartial]);

  useEffect(() => {
    if (sessionRef.current) sessionRef.current.vadThreshold = threshold;
  }, [threshold]);

  const startCall = async () => {
    setLogs([]);
    setBotPartial("");
    const session = new CallSession({
      onStatusChange: setStatus,
      onLog: (entry) => setLogs((prev) => [...prev, entry]),
      onBotPartial: setBotPartial,
      onLevel: setLevel,
    });
    session.vadThreshold = threshold;
    sessionRef.current = session;
    await session.start(tenantId);
  };

  const endCall = () => {
    sessionRef.current?.end();
    sessionRef.current = null;
    setLevel(0);
  };

  const isLive = status === "connecting" || status === "connected";

  return (
    <div className="page call-test">
      <div className="page-header">
        <h2>Call Test</h2>
        <span className="muted">Test any tenant's bot from this browser tab - mic in, synthesized speech out.</span>
      </div>

      <div className="call-controls panel-section">
        <label>Tenant</label>
        <select value={tenantId} onChange={(e) => setTenantId(e.target.value)} disabled={isLive}>
          <option value="">(none - generic defaults)</option>
          {(tenantIds ?? []).map((id) => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>

        <div className="field-row-line" style={{ marginTop: 10 }}>
          {!isLive ? (
            <button type="button" onClick={() => void startCall()}>Start call</button>
          ) : (
            <button type="button" className="danger" onClick={endCall}>End call</button>
          )}
          <span className={`status-pill status-${status}`}>{status}</span>
        </div>

        <label style={{ marginTop: 12 }}>Mic level</label>
        <div className="level-meter">
          <div className="level-meter-fill" style={{ width: `${Math.min(100, (level / 4000) * 100)}%` }} />
          <div className="level-meter-threshold" style={{ left: `${Math.min(100, (threshold / 4000) * 100)}%` }} />
        </div>

        <label>
          Barge-in threshold (RMS): {threshold}
          {" - "}
          <a
            href="#"
            className="link-button"
            onClick={(e) => {
              e.preventDefault();
              setThreshold(DEFAULT_VAD_THRESHOLD);
            }}
          >
            reset
          </a>
        </label>
        <input
          type="range"
          min={50}
          max={4000}
          step={50}
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
        />
        <p className="muted">
          Lower = more sensitive to interruption. This machine's mic has needed values as low as ~93 in the past
          (see CLAUDE.md) - if barge-in never fires, try lowering this while watching the level meter.
        </p>
      </div>

      <div className="call-transcript">
        {logs.length === 0 && !botPartial && (
          <p className="muted panel-section">Start a call and speak into your mic. Replies appear here as the bot speaks them.</p>
        )}
        {logs.map((entry) => (
          <div key={entry.id} className={`transcript-line transcript-${entry.kind}`}>
            <span className="transcript-kind">{entry.kind === "caller" ? "You" : entry.kind === "bot" ? "Bot" : entry.kind === "error" ? "Error" : "System"}</span>
            <span className="transcript-text">{entry.text}</span>
          </div>
        ))}
        {botPartial && (
          <div className="transcript-line transcript-bot transcript-live">
            <span className="transcript-kind">Bot</span>
            <span className="transcript-text">{botPartial}</span>
          </div>
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
