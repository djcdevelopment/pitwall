---
name: Phosphor Telemetry HUD
colors:
  surface: '#101412'
  surface-dim: '#101412'
  surface-bright: '#363a38'
  surface-container-lowest: '#0b0f0d'
  surface-container-low: '#181c1a'
  surface-container: '#1c201e'
  surface-container-high: '#272b28'
  surface-container-highest: '#323633'
  on-surface: '#e0e3df'
  on-surface-variant: '#b9cbb9'
  inverse-surface: '#e0e3df'
  inverse-on-surface: '#2d312f'
  outline: '#849585'
  outline-variant: '#3b4b3d'
  surface-tint: '#00e479'
  primary: '#f1ffef'
  on-primary: '#003919'
  primary-container: '#00ff88'
  on-primary-container: '#007139'
  inverse-primary: '#006d37'
  secondary: '#bdf4ff'
  on-secondary: '#00363d'
  secondary-container: '#00e3fd'
  on-secondary-container: '#00616d'
  tertiary: '#fffaf8'
  on-tertiary: '#452b00'
  tertiary-container: '#ffd8a7'
  on-tertiary-container: '#875800'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#60ff99'
  primary-fixed-dim: '#00e479'
  on-primary-fixed: '#00210c'
  on-primary-fixed-variant: '#005228'
  secondary-fixed: '#9cf0ff'
  secondary-fixed-dim: '#00daf3'
  on-secondary-fixed: '#001f24'
  on-secondary-fixed-variant: '#004f58'
  tertiary-fixed: '#ffddb4'
  tertiary-fixed-dim: '#ffb952'
  on-tertiary-fixed: '#291800'
  on-tertiary-fixed-variant: '#633f00'
  background: '#101412'
  on-background: '#e0e3df'
  surface-variant: '#323633'
typography:
  display-lg:
    fontFamily: Space Mono
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Space Mono
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.02em
  display-md:
    fontFamily: Space Mono
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Space Mono
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 28px
    letterSpacing: 0.02em
  headline-md:
    fontFamily: Space Mono
    fontSize: 18px
    fontWeight: '700'
    lineHeight: 24px
    letterSpacing: 0.04em
  title-sm:
    fontFamily: JetBrains Mono
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.05em
  body-lg:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0.01em
  body-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0.02em
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.08em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 12px
    letterSpacing: 0.1em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 9px
    fontWeight: '500'
    lineHeight: 12px
    letterSpacing: 0.12em
spacing:
  gutter: 0.5rem
  gutter-mobile: 0.375rem
  margin: 1rem
  margin-mobile: 0.75rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system channels the tactile authority of mid-century cathode ray oscilloscopes and calibrated benchtop instrumentation, refitted for modern mobile-first machine learning and edge telemetry. It rejects generic corporate minimalism in favor of an exacting, high-density telemetry HUD. The design language merges industrial physical instrumentation—skeuomorphic graticule references, segmented bar meters, rotary stepping metaphors—with ultra-crisp digital cybernetics.

### Personality & Tone
- **Exacting & Calibrated:** Unapologetically technical; data is presented without decorative smoothing or arbitrary abstraction.
- **Luminescent & Tactical:** Visual hierarchy stems directly from phosphor decay, voltage traces, and emission intensity against absolute non-reflective glass.
- **Instrument-Grade Reliability:** Every control, read-out, and pip communicates physical state and instant tactile feedback.

### Visual Style
- **Aesthetic Movement:** CRT Cyber-Instrument / Tactical Laboratory HUD.
- **Atmosphere:** Deep void glass substrates overlayed with high-luminance phosphor emissions, hairline graticules, calibrated tick subdivisions, and tabular telemetry readouts.
- **Scanlines & CRT Texture:** Structural micro-textures (0.5px scanline masks, faint barrel vignette at display bounds) establish authentic optical depth without occluding legibility.

## Colors

The palette simulates phosphor emission spectrums excited by an electron gun, operating in an optical void. Contrast ratios meet strict WCAG AAA requirements against dark substrates.

### Spectral Roles
- **Primary Phosphor (`#00FF88`):** Nominal beam emission. Used for active traces, primary telemetry digits, confirmed states, and standard waveform paths.
- **Secondary Beam (`#00E5FF`):** Auxiliary channel. Dedicated to secondary vector overlays, differential delta metrics, clocks, and secondary bus interfaces.
- **Tertiary Beam (`#FFAA00`):** Thermal/load alert. Signifies threshold overshoots, saturation alerts, high-frequency bus collisions, and armed states.
- **Critical Beam (`#FF3344`):** Emergency cutoff, hardware clip, voltage overload, and unrecoverable dropouts.
- **Neutral Substrate (`#090D0B`):** Deep cathode tube void; ultra-dark onyx infused with raw carbon-green undertones.

### Attenuation & Trace Tiers
- **Void Surface 0:** `#090D0B` (Base chassis floor).
- **Substrate Surface 1:** `#0D1410` (Panel backplanes, isolated instrument frames).
- **Substrate Surface 2:** `#131C17` (Active readouts, inset meters, container fills).
- **Graticule Axis / Inactive Segments:** `rgba(0, 255, 136, 0.12)` (Zero-excitation grid matrix, unlit LED segments).
- **Dormant Text / Sub-labels:** `rgba(0, 255, 136, 0.45)` (Inactive or secondary laboratory nomenclature).
- **Active Phosphor Beam:** `#00FF88` with localized multi-stage glow drop-shadows.

## Typography

Typography functions as visual digital telemetry. All numerical data, metrics, channels, and logs strictly enforce fixed-pitch monospaced layout (`font-feature-settings: "tnum" 1, "zero" 1`).

### Typographic Hierarchy & Treatment
- **Display & Headline Roles:** Driven by `Space Mono` for its mechanical, geometric character. Used for core voltage, cycle metrics, and station header callouts. All headlines display in full uppercase with positive tracking to evoke calibrated hardware equipment plaques.
- **Telemetry Readouts & Logs:** Driven by `JetBrains Mono` for maximum micro-legibility at compact densities, zero-slashed numbers, and distinct glyph differentiation (`1`, `l`, `I`).
- **Micro Labels (`label-sm`, `label-md`):** Fixed uppercase annotations for unit multipliers (e.g., `mV/DIV`, `GS/s`, `dBm`, `TOK/s`). Positioned directly adjacent to tick divisions or status indicators.

## Layout & Spacing

The layout is built on an ultra-compact 4px baseline sub-grid that mimics physical laboratory instrument chassis racks. Visual real estate prioritizes uninterrupted waveform vectors and dense numerical data matrices.

### Grid & Density Architecture
- **Mobile Grid:** 4-column layout with 6px gutters and 12px margins. Modules clamp edge-to-edge with visible hairline division channels.
- **Tablet / Expanded Screen:** 8 to 12 columns with 8px gutters, allowing parallel channel scopes alongside control banks.
- **Chassis Partitioning:** Content is segmented into discrete instrument pods rather than fluid cards. Each pod is bounded by precise 1px borders, functioning as a modular telemetry cartridge.
- **Ergonomics & Touch Accessibility:** While visible graphics, labels, and readouts are micro-scaled for high density, all interactive touch areas enforce a strict minimum bounding box of 48px × 48px using invisible padding extensions.

## Elevation & Depth

Elevation in this design system is non-Euclidean: rather than lifting surfaces along a physical Z-axis using broad ambient drop shadows, depth is manifested through electron luminescence, optical lens diffusion, and recessed structural cutouts.

### Depth Mechanisms
- **Sub-chassis Inset:** Wells and meter cavities use inner inset borders (`inset 0 1px 2px rgba(0, 0, 0, 0.9)`) combined with a dark carbon flood `#060907` to place them physically behind the display plane.
- **Graticule Underlay:** The oscilloscope coordinate grid sits directly below the trace layer at 10-15% phosphor opacity with 1px dotted or dashed alignments.
- **Phosphor Bloom (Luminescent Elevation):** Interactive and energetic elements project optical emission outward:
  - *Standard Active Glow:* `0 0 6px rgba(0, 255, 136, 0.45), 0 0 14px rgba(0, 255, 136, 0.18)`
  - *Saturated Beam Flare:* `0 0 2px #FFFFFF, 0 0 8px #00FF88, 0 0 20px rgba(0, 255, 136, 0.6)`
  - *Warning/Amber Alert:* `0 0 6px rgba(255, 170, 0, 0.5), 0 0 16px rgba(255, 170, 0, 0.2)`
- **CRT Glass Glare & Scanlines:** Top-level viewport overlay utilizing a repeating linear gradient of 1px scanlines at 4% opacity, bounded by an ultra-subtle inward bezel vignette (`box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.85)`).

## Shapes

The shape system adopts a zero-radius, hard-line industrial architecture (`roundedness: 0`). Curved, organic forms conflict with precision measurement; geometry is strictly angular, orthogonal, and calibrated.

### Shape Characteristics
- **Right Angles (0px Corner Radius):** All panels, containers, buttons, and segmented displays feature raw 90° corners.
- **Beveled Chamfers:** For primary trigger zones, alert dialogs, and active mode toggles, an optional 45-degree chamfer (4px to 6px corner cut via `clip-path: polygon(...)`) communicates physical military-spec chassis manufacturing.
- **Structural Reticles & Crosshairs:** Panel boundaries feature decorative L-shaped corner brackets and crosshair axis registration markers (`+`) at coordinate intersections.

## Components

### 1. Actuator Buttons
- **Visuals:** Hard 1px borders in `rgba(0, 255, 136, 0.4)` with `#0D1410` backplane fill. Text is uppercase `label-lg` with `letter-spacing: 0.1em`.
- **States:**
  - *Idle:* Dim green border, faint text glow.
  - *Pressed / Armed:* Solid `#00FF88` background flood, `#090D0B` inverted text, intense outer bloom.
  - *Standby / Disabled:* 1px dotted border in `rgba(0, 255, 136, 0.15)`, text at 20% opacity.
- **Hit Target:** Visual height can be 32px-36px, with touch container padded out to 48px minimum.

### 2. Segmented LED Pip Bars (Linear Gauges)
- **Structure:** Horizontal or vertical discrete segment arrays (12, 16, or 24 pips) separated by 1px non-conductive gaps.
- **Behavior:**
  - Dormant pips render in unlit dark emerald (`#0E1712`).
  - Active pips light up sequentially in `#00FF88`.
  - Nominal range transitions to `#00E5FF` for mid-peaks and flashes `#FFAA00` or `#FF3344` at saturation (last 2-3 pips).

### 3. Oscilloscope Graticule Display Container
- **Substrate:** `#050806` base with 0.5px dashed vertical/horizontal coordinate grid spaced at precise 20px intervals.
- **Perimeter:** Outer border with centimeter/millivolt graduation ticks along the top and left axes.
- **Corner Anchors:** Outer HUD bounds marked with 6px tick reticles (`+` and `L` indicators) displaying real-time coordinate offsets (`X-POS`, `Y-SCALE`).

### 4. Interactive Channel Chips & Selectors
- **Visuals:** Ultra-compact square or chamfered badges containing channel labels (e.g., `CH-A`, `CH-B`, `TRIG-EXT`).
- **Active State:** Inset active indicator dot (3px × 3px solid block) accompanied by a 1px solid active beam border matching the assigned channel color (`#00FF88` or `#00E5FF`).

### 5. Numerical Steppers & Rotary Touch Dials
- **Structure:** Touch-optimized circular or horizontal sweep controls for scrubbing time-base (`ms/DIV`) and voltage divisions.
- **Display:** Central high-contrast value readout displaying trailing units in smaller superscript `label-sm`.
- **Haptics / Interaction:** Dragging triggers discrete simulated mechanical detent steps with high-contrast pip markers ticking sequentially around the sweep perimeter.

### 6. Telemetry Terminal Feed & Log Rows
- **Structure:** Borderless, zero-padding monospaced stream with 1px border dividers in `rgba(0, 255, 136, 0.08)`.
- **Formatting:** Each row begins with a fixed-width timestamp `[HH:MM:SS.sss]` in cyan (`#00E5FF`), followed by the channel tag in amber or green, concluding with dynamic tabular payload values.