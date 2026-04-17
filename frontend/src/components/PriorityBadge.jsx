import React from "react";

const STYLES = {
    HIGH: { bg: "#FEE2E2", fg: "#991B1B", border: "#FCA5A5", label: "ALTA" },
    MEDIUM: { bg: "#FEF3C7", fg: "#92400E", border: "#FCD34D", label: "MEDIA" },
    LOW: { bg: "#DBEAFE", fg: "#1E40AF", border: "#93C5FD", label: "BAJA" },
};

export default function PriorityBadge({ level = "LOW", testid }) {
    const style = STYLES[level] || STYLES.LOW;
    return (
        <span
            data-testid={testid || `priority-badge-${level.toLowerCase()}`}
            className="inline-flex items-center px-2.5 py-1 text-[10px] font-mono font-semibold tracking-widest"
            style={{
                background: style.bg,
                color: style.fg,
                border: `1px solid ${style.border}`,
            }}
        >
            {style.label}
        </span>
    );
}

export const IntentChip = ({ intent }) => {
    const map = {
        Alta: { bg: "#DCFCE7", fg: "#166534", border: "#86EFAC" },
        Media: { bg: "#F4F4F5", fg: "#3F3F46", border: "#D4D4D8" },
        Baja: { bg: "#FFFFFF", fg: "#71717A", border: "#E4E4E7" },
    };
    const style = map[intent] || map.Media;
    return (
        <span
            data-testid={`intent-chip-${intent?.toLowerCase()}`}
            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
            style={{
                background: style.bg,
                color: style.fg,
                border: `1px solid ${style.border}`,
            }}
        >
            {intent}
        </span>
    );
};
