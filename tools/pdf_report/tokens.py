"""
Design tokens and shared helpers for the PDF report (colors, claim states, HTML escape).
"""
# Design tokens
_N = "#0B1437"       # navy
_S = "#1E293B"       # slate
_A = "#3B82F6"       # accent
_AD = "#1D4ED8"     # accent dark
_BG = "#F8FAFC"     # light bg
_BD = "#E2E8F0"     # border
_T = "#1E293B"      # text
_TL = "#64748B"     # text light
_G = "#059669"      # green
_Y = "#D97706"      # yellow
_R = "#DC2626"      # red
_P = "#7C3AED"      # purple
_O = "#EA580C"      # orange

# Claim lifecycle states
STATE_STABLE = "stable"
STATE_TENTATIVE = "tentative"
STATE_CONTESTED = "contested"
STATE_DECAYING = "decaying"

STATE_COLORS = {
    STATE_STABLE: _G,
    STATE_TENTATIVE: _Y,
    STATE_CONTESTED: _O,
    STATE_DECAYING: _R,
}
STATE_BG = {
    STATE_STABLE: "#ECFDF5",
    STATE_TENTATIVE: "#FFFBEB",
    STATE_CONTESTED: "#FFF7ED",
    STATE_DECAYING: "#FEF2F2",
}


def esc(s: str) -> str:
    """Escape for HTML text/attributes."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
