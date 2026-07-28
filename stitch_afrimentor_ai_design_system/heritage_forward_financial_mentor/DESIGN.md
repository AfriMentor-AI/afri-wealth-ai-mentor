---
name: Heritage-Forward Financial Mentor
colors:
  surface: '#fcf9f3'
  surface-dim: '#dcdad4'
  surface-bright: '#fcf9f3'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3ed'
  surface-container: '#f0eee8'
  surface-container-high: '#ebe8e2'
  surface-container-highest: '#e5e2dc'
  on-surface: '#1c1c18'
  on-surface-variant: '#504536'
  inverse-surface: '#31312d'
  inverse-on-surface: '#f3f0ea'
  outline: '#827564'
  outline-variant: '#d4c4b0'
  surface-tint: '#7e5700'
  primary: '#7e5700'
  on-primary: '#ffffff'
  primary-container: '#c8922a'
  on-primary-container: '#462f00'
  inverse-primary: '#f8bc51'
  secondary: '#1b6d24'
  on-secondary: '#ffffff'
  secondary-container: '#a0f399'
  on-secondary-container: '#217128'
  tertiary: '#5f5e5e'
  on-tertiary: '#ffffff'
  tertiary-container: '#9d9b9b'
  on-tertiary-container: '#343333'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdeab'
  primary-fixed-dim: '#f8bc51'
  on-primary-fixed: '#281900'
  on-primary-fixed-variant: '#5f4100'
  secondary-fixed: '#a3f69c'
  secondary-fixed-dim: '#88d982'
  on-secondary-fixed: '#002204'
  on-secondary-fixed-variant: '#005312'
  tertiary-fixed: '#e5e2e1'
  tertiary-fixed-dim: '#c8c6c5'
  on-tertiary-fixed: '#1c1b1b'
  on-tertiary-fixed-variant: '#474646'
  background: '#fcf9f3'
  on-background: '#1c1c18'
  surface-variant: '#e5e2dc'
typography:
  headline-xl:
    fontFamily: Be Vietnam Pro
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Be Vietnam Pro
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: Be Vietnam Pro
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 34px
  title-md:
    fontFamily: Be Vietnam Pro
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-sm:
    fontFamily: Inter
    fontSize: 13px
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
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 48px
  margin-mobile: 20px
  gutter: 16px
---

## Brand & Style
The design system is built on a philosophy of "Dignified Optimism." It avoids the cold, sterile aesthetics of traditional fintech in favor of a warm, culturally resonant atmosphere that reflects growth and communal wisdom. The visual language balances modern efficiency with West African heritage, utilizing clean lines and organic textures.

The style is primarily **Minimalist-Tactile**, prioritizing flat color blocks for performance on lower-end devices while using subtle Adinkra line-art (specifically the Sankofa bird) to denote sections of reflection and learning. The goal is to evoke the feeling of a trusted mentor sitting across from the user in a sun-drenched space—professional yet deeply personal.

## Colors
The palette is rooted in the earth and the sun. The primary **Confident Gold (#C8922A)** serves as the "mentor color," used for key calls-to-action and success states. The background is never pure white, but a **Warm Cream (#FDFAF4)** to reduce eye strain and feel more like traditional paper or fabric.

A set of muted, high-readability pastels is used to categorize financial life-stages and app sections. These should be used as background floods for cards or chips, paired with their respective deep-toned text variants to ensure WCAG AA accessibility on all device types.

## Typography
The system uses a humanist approach to type. **Be Vietnam Pro** provides a contemporary, friendly geometric touch for headlines, while **Inter** ensures maximum legibility for financial data and chat interfaces across various screen densities.

Headlines are intentionally oversized to provide clear visual hierarchy and a sense of "dignity" in the content. Body text utilizes a generous 1.5x-1.6x line-height ratio to ensure that financial advice is easy to digest, particularly for users on small or lower-resolution screens.

## Layout & Spacing
The layout follows a **Fluid Grid** model optimized for mobile-first usage. A standard 4-column grid is used for mobile devices with a 20px outer margin. Spacing is strictly based on a 4px baseline grid to maintain rhythm.

To accommodate low-end devices and reduce "visual noise," the system relies on generous vertical padding (`xl`) between major sections rather than heavy divider lines. This creates a breathable, calm interface that guides the user’s eye downward through the financial narrative.

## Elevation & Depth
In alignment with the goal of being accessible to low-end devices, this design system avoids heavy drop-shadows and complex blurs. Instead, depth is achieved through **Tonal Layers**.

- **Level 0 (Base):** Warm Cream (#FDFAF4) background.
- **Level 1 (Cards/Containers):** Warm Sand (#F5E6C8) or flat semantic pastels.
- **Level 2 (Active elements):** Subtle, 1px solid borders in a slightly darker shade of the surface color to define boundaries without requiring GPU-intensive rendering.

Visual focus is directed via color saturation rather than physical elevation.

## Shapes
The shape language is "Soft-Organic." The `rounded-md` (0.5rem) setting is used for primary containers and cards, while `rounded-xl` (1.5rem) is used for buttons and interactive elements to make them feel approachable and "tap-friendly."

Adinkra-inspired line art should be treated as a "background shape" rather than an image—using 1px or 1.5px stroke widths in the same color as the text but at 15% opacity.

## Components

### Interactive Elements
- **Buttons:** Large, pill-shaped (44px min height). The primary button uses the Confident Gold with deep charcoal text for maximum contrast.
- **Quick-Reply Chips:** Rounded containers with a 1px border. Use the "Learning" or "Community" semantic colors for the background.
- **Tap Targets:** All icons and interactive links must maintain a minimum 44x44px invisible hit area.

### Financial Visualization
- **Goal Progress Rings:** Thick, 8px stroke weight. Use Sage Green for progress and the Warm Sand for the empty track. No gradients.
- **Milestone Road:** A simple, vertical 2px dashed line connecting circular nodes. Active nodes are filled with Gold; upcoming nodes are hollow with a 2px stroke.

### Information Containers
- **Persona Cards:** Use a flat background flood of "Encouragement" (Rose) or "Community" (Sky). Avatars are circular with a 2px Gold border.
- **Skeleton States:** Simple, flat gray-wash rectangles (#E0E0E0) that match the exact border-radius of the component they represent to prevent layout shift on slow connections.

### Navigation
- **Bottom Tab Bar:** Fixed, flat background (#FDFAF4) with a 1px top border. Icons are simple line-art; the active state is indicated by a Gold icon and a small 4px dot underneath.