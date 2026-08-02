"""
Real WCAG 2.1 contrast ratio calculation (relative luminance formula,
not an approximation) for every foreground/background token pair the
app actually uses. Run against the literal hex values in globals.css.
"""

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def relative_luminance(rgb):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

def contrast_ratio(hex1, hex2):
    l1 = relative_luminance(hex_to_rgb(hex1))
    l2 = relative_luminance(hex_to_rgb(hex2))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

# Heritage-Forward (light) tokens, verbatim from app/globals.css
heritage = {
    "surface": "#fcf9f3", "surface-container-low": "#f6f3ed", "surface-container": "#f0eee8",
    "on-surface": "#1c1c18", "on-surface-variant": "#504536",
    "primary": "#7e5700", "on-primary": "#ffffff",
    "primary-container": "#c8922a", "on-primary-container": "#462f00",
    "secondary": "#1b6d24", "on-secondary": "#ffffff",
    "secondary-container": "#a0f399", "on-secondary-container": "#217128",
    "tertiary": "#5f5e5e", "on-tertiary": "#ffffff",
    "tertiary-container": "#9d9b9b", "on-tertiary-container": "#343333",
    "error": "#ba1a1a", "on-error": "#ffffff",
    "error-container": "#ffdad6", "on-error-container": "#93000a",
}

# Nocturnal Heritage (dark) tokens, verbatim from app/globals.css
nocturnal = {
    "surface": "#17140f", "surface-container-low": "#1f1b14", "surface-container": "#231e17",
    "on-surface": "#f3f0ea", "on-surface-variant": "#d4c4b0",
    "primary": "#f8bc51", "on-primary": "#462f00",
    "primary-container": "#c8922a", "on-primary-container": "#462f00",
    "secondary": "#88d982", "on-secondary": "#00390a",
    "secondary-container": "#217128", "on-secondary-container": "#a3f69c",
    "tertiary": "#c8c6c5", "on-tertiary": "#313030",
    "tertiary-container": "#474646", "on-tertiary-container": "#e5e2e1",
    "error": "#ffb4ab", "on-error": "#690005",
    "error-container": "#93000a", "on-error-container": "#ffdad6",
}

# Every foreground/background pair actually used together in the app's
# components (Button variants, Chip, cards, MilestoneRoad nodes, badges).
pairs = [
    ("on-surface", "surface", "Body text on page background"),
    ("on-surface-variant", "surface", "Muted/secondary text on page background"),
    ("on-surface", "surface-container-low", "Card text on card background"),
    ("on-primary", "primary", "Button.primary text"),
    ("on-primary-container", "primary-container", "Button.cta text / persona 'Recommended' card"),
    ("on-secondary", "secondary", "ProgressRing/MilestoneRoad 'done' text"),
    ("on-secondary-container", "secondary-container", "Goals 'Debt Reduction' card text"),
    ("on-tertiary-container", "tertiary-container", "Milestone 'upcoming' hollow node text"),
    ("on-error", "error", "Error state text"),
    ("on-error-container", "error-container", "Commitment 'blocked' card text"),
    ("primary", "surface", "CHIOMA brand wordmark on page background"),
]

WCAG_AA_NORMAL = 4.5
WCAG_AA_LARGE = 3.0

for theme_name, theme in [("Heritage-Forward (light)", heritage), ("Nocturnal Heritage (dark)", nocturnal)]:
    print(f"\n=== {theme_name} ===")
    for fg, bg, label in pairs:
        ratio = contrast_ratio(theme[fg], theme[bg])
        status = "PASS" if ratio >= WCAG_AA_NORMAL else ("PASS (large text only)" if ratio >= WCAG_AA_LARGE else "FAIL")
        marker = "✓" if ratio >= WCAG_AA_NORMAL else ("~" if ratio >= WCAG_AA_LARGE else "✗")
        print(f"  {marker} {label:50s} {fg} on {bg}: {ratio:.2f}:1  [{status}]")
