import { ClipboardList, GitBranch, MessageSquare, PhoneForwarded, Square, Zap } from "lucide-react";
import type { ComponentType } from "react";
import type { NodeType } from "../types";

// Matches FlowNodeBox.tsx's TYPE_COLOR exactly - same node type, same color,
// whether it's a palette button or a box on the canvas.
const TYPES: { type: NodeType; label: string; icon: ComponentType<{ size?: number; color?: string }>; color: string }[] = [
  { type: "collect", label: "Collect", icon: ClipboardList, color: "#2563eb" },
  { type: "say", label: "Say", icon: MessageSquare, color: "#059669" },
  { type: "action", label: "Action", icon: Zap, color: "#d97706" },
  { type: "branch", label: "Branch", icon: GitBranch, color: "#7c3aed" },
  { type: "handoff", label: "Handoff", icon: PhoneForwarded, color: "#dc2626" },
  { type: "end", label: "End", icon: Square, color: "#475569" },
];

interface Props {
  onAdd: (type: NodeType) => void;
}

export default function NodePalette({ onAdd }: Props) {
  return (
    <div className="palette">
      {TYPES.map((t) => {
        const Icon = t.icon;
        return (
          <button key={t.type} type="button" onClick={() => onAdd(t.type)}>
            <Icon size={14} color={t.color} />
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
