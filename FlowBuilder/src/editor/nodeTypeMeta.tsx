import { ClipboardList, GitBranch, MessageSquare, PhoneForwarded, Square, Zap } from "lucide-react";
import type { ComponentType } from "react";
import type { NodeType } from "../types";

export interface NodeTypeMeta {
  label: string;
  color: string;
  icon: ComponentType<{ size?: number; color?: string }>;
}

// Single source of truth for node-type identity (color + icon) - the
// canvas box, the palette button, and the editor drawer header all read
// from here, so "collect is blue" never drifts between them.
export const NODE_TYPE_META: Record<NodeType, NodeTypeMeta> = {
  collect: { label: "Collect", color: "#2563eb", icon: ClipboardList },
  say: { label: "Say", color: "#059669", icon: MessageSquare },
  action: { label: "Action", color: "#d97706", icon: Zap },
  branch: { label: "Branch", color: "#7c3aed", icon: GitBranch },
  handoff: { label: "Handoff", color: "#dc2626", icon: PhoneForwarded },
  end: { label: "End", color: "#475569", icon: Square },
};
