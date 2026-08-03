interface Props {
  clientProblems: string[];
  serverProblems: string[] | null;
}

export default function ValidationPanel({ clientProblems, serverProblems }: Props) {
  const ok = clientProblems.length === 0 && (serverProblems === null || serverProblems.length === 0);

  return (
    <div className={`validation-panel ${ok ? "ok" : "problems"}`}>
      <h4>{ok ? "Graph looks sound" : "Problems"}</h4>
      {clientProblems.length > 0 && (
        <ul>
          {clientProblems.map((p, i) => (
            <li key={`c-${i}`}>{p}</li>
          ))}
        </ul>
      )}
      {serverProblems && serverProblems.length > 0 && (
        <>
          <p className="muted">Rejected by server on last save:</p>
          <ul>
            {serverProblems.map((p, i) => (
              <li key={`s-${i}`}>{p}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
