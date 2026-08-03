import type { NodeType } from "../types";
import { NODE_TYPE_META } from "./nodeTypeMeta";

const TYPES: NodeType[] = ["collect", "say", "action", "branch", "handoff", "end"];

interface Props {
  onAdd: (type: NodeType) => void;
}

export default function NodePalette({ onAdd }: Props) {
  return (
    <div className="palette">
      {TYPES.map((type) => {
        const meta = NODE_TYPE_META[type];
        const Icon = meta.icon;
        return (
          <button key={type} type="button" onClick={() => onAdd(type)}>
            <Icon size={14} color={meta.color} />
            {meta.label}
          </button>
        );
      })}
    </div>
  );
}
