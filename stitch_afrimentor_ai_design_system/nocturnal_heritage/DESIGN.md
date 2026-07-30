---
name: Nocturnal Heritage
colors:
  surface: '#121414'
  surface-dim: '#121414'
  surface-bright: '#38393a'
  surface-container-lowest: '#0d0f0f'
  surface-container-low: '#1a1c1c'
  surface-container: '#1e2020'
  surface-container-high: '#282a2b'
  surface-container-highest: '#333535'
  on-surface: '#e2e2e2'
  on-surface-variant: '#d4c4b0'
  inverse-surface: '#e2e2e2'
  inverse-on-surface: '#2f3131'
  outline: '#9c8f7c'
  outline-variant: '#504536'
  surface-tint: '#f8bc51'
  primary: '#f8bc51'
  on-primary: '#422c00'
  primary-container: '#c8922a'
  on-primary-container: '#462f00'
  inverse-primary: '#7e5700'
  secondary: '#c8c6c5'
  on-secondary: '#313030'
  secondary-container: '#474746'
  on-secondary-container: '#b7b5b4'
  tertiary: '#c8c6c6'
  on-tertiary: '#303030'
  tertiary-container: '#9d9b9b'
  on-tertiary-container: '#333333'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdeab'
  primary-fixed-dim: '#f8bc51'
  on-primary-fixed: '#281900'
  on-primary-fixed-variant: '#5f4100'
  secondary-fixed: '#e5e2e1'
  secondary-fixed-dim: '#c8c6c5'
  on-secondary-fixed: '#1c1b1b'
  on-secondary-fixed-variant: '#474746'
  tertiary-fixed: '#e4e2e1'
  tertiary-fixed-dim: '#c8c6c6'
  on-tertiary-fixed: '#1b1c1c'
  on-tertiary-fixed-variant: '#474747'
  background: '#121414'
  on-background: '#e2e2e2'
  surface-variant: '#333535'
typography:
  headline-xl:
    fontFamily: Be Vietnam Pro
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Be Vietnam Pro
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Be Vietnam Pro
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
  headline-md:
    fontFamily: Be Vietnam Pro
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Be Vietnam Pro
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Be Vietnam Pro
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Be Vietnam Pro
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Be Vietnam Pro
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 48px
  xl: 80px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 64px
---

## Brand & Style
This design system translates a dignified, heritage-driven financial mentorship experience into a high-end dark mode environment. The brand personality is authoritative yet approachable, evoking the feeling of a private library or a high-end study at twilight. It targets users seeking financial wisdom with a sense of longevity and warmth rather than cold, clinical data.

The visual style is **Corporate Modern with Tactile influences**, utilizing deep obsidian surfaces to provide a focused, low-strain environment. The emotional response is one of security, optimism, and quiet confidence. Large typography and generous whitespace prevent the dark theme from feeling cramped, while subtle ochre accents provide a "guiding light" through the financial journey.

## Colors
The palette is anchored by a deep obsidian background, replacing traditional whites with rich, layered dark tones to maintain depth.

- **Primary (Sunbaked Ochre):** Used for primary actions, progress indicators, and key brand moments. It retains its warmth but glows against the dark background.
- **Surface Palette:** We use a tiered system of charcoal and obsidian. The base layer is the darkest, with higher "elevation" layers becoming progressively lighter to imply physical stacking.
- **Semantic Palette:** These colors have been tuned for dark mode by increasing their luminance and slightly desaturating them. This ensures they remain legible and vibrant without "vibrating" against the dark surfaces or appearing muddy.
- **Typography Colors:** Primary text uses a soft off-white (#E5E5E5) to reduce eye strain compared to pure white, while secondary text uses a muted silver.

## Typography
The typography utilizes **Be Vietnam Pro** across all levels to maintain a contemporary yet friendly character. 

- **Headlines:** Use tighter letter spacing and heavier weights to command attention. They should feel architectural and sturdy.
- **Body Text:** Leading is generous (1.5x) to ensure long-form financial advice remains readable in a light-on-dark context.
- **Labels:** Small caps or medium weights are used for data visualization labels to provide clear contrast against the rich background textures.
- **Scalability:** On mobile devices, the largest display type scales down significantly to avoid awkward line breaks, maintaining a maximum width of 90% of the viewport.

## Layout & Spacing
The layout follows a **Fluid Grid** philosophy with fixed maximum widths for content containers to ensure readability.

- **Grid:** A 12-column grid is used for desktop, collapsing to 4 columns on mobile. 
- **Rhythm:** Spacing follows an 8px base unit. Vertical rhythm is strictly enforced to create a sense of professional order.
- **Negative Space:** Generous "breathing room" (the 'lg' and 'xl' units) is used between major sections to emphasize the premium, unhurried nature of the mentorship experience.
- **Adaptivity:** On mobile, margins shrink to 16px, and vertical gaps between cards are reduced to 12px to maximize screen real estate while keeping the tactile feel.

## Elevation & Depth
In this dark system, depth is communicated through **Tonal Layering** and **Ambient Glows** rather than traditional drop shadows.

- **Layers:** The background is #0D0D0D. Primary containers use #1A1A1A. Elevated elements (like modals or hovered cards) use #2D2D2D.
- **Inner Glows:** To give components a "heritage" feel, a very subtle 1px inner border (opacity 10%) in the primary ochre color is applied to top-level cards, simulating a light catching the edge of a physical object.
- **Shadows:** Where shadows are used, they are large, soft, and tinted with the primary ochre color at a very low (5%) opacity, creating a subtle "warmth" behind active components.

## Shapes
The shape language is defined by **Rounded Eight** (0.5rem / 8px) corners, striking a balance between the precision of financial tools and the softness of a human mentor.

- **Small Components:** Buttons and input fields use the base 8px radius.
- **Containers:** Large cards and section wrappers use `rounded-lg` (16px) to create a clear visual containment.
- **Interactive Elements:** Selection states and focus rings follow the parent's corner radius exactly to maintain a clean, nested appearance.

## Components
- **Buttons:** Primary buttons are solid Sunbaked Ochre with dark obsidian text for maximum contrast. Secondary buttons use a ghost style with an ochre border.
- **Cards:** Use the #1A1A1A surface color. Card titles use `headline-md`. Borders should be minimal or non-existent, relying on tonal changes to define edges.
- **Input Fields:** Backgrounds are slightly darker than the card surface (#121212) with a 1px border that glows ochre upon focus.
- **Chips/Badges:** Use the semantic palette (Sage, Rose, etc.) with a 15% opacity background and a 100% opacity text color for a modern "pill" look that is easy on the eyes.
- **Lists:** Separators are low-contrast (#333333) and 1px thick. List items feature generous padding (16px) to ensure touch targets are accessible and the UI feels "airy."
- **Progress Bars:** Utilize the primary ochre for the "fill" and a deep charcoal for the "track," ensuring financial goals feel like they are "filling with light."