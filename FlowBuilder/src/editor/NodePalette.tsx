import type { NodeType } from "../types";

const TYPES: { type: NodeType; label: string }[] = [
  { type: "collect", label: "+ Collect" },
  { type: "say", label: "+ Say" },
  { type: "action", label: "+ Action" },
  { type: "branch", label: "+ Branch" },
  { type: "handoff", label: "+ Handoff" },
  { type: "end", label: "+ End" },
];

interface Props {
  onAdd: (type: NodeType) => void;
}

export default function NodePalette({ onAdd }: Props) {
  return (
    <div className="palette">
      {TYPES.map((t) => (
        <button key={t.type} type="button" onClick={() => onAdd(t.type)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}
