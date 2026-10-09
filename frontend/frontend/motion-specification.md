# BUBBLES Motion System Specification

## Overview

This specification defines the refined motion system for Bubbles' signature landing page, built on React + Framer Motion + Three.js. All animations are performant, respect `prefers-reduced-motion`, and follow the token-based design from `frontend/tokens.css` and `frontend/app/motion.css`.

---

## 1. Animation Tokens

### Duration Tokens (from `tokens.css`)

| Token | Value | Usage |
|-------|-------|-------|
| `--duration-instant` | `0ms` | State flips, focus rings, toggles |
| `--duration-fast` | `120ms` | Press/hover feedback, modal entrances |
| `--duration-normal` | `200ms` | Standard component motion, card entrances |
| `--duration-slow` | `300ms` | Page/section entrances, deliberate moments |
| `--duration-slower` | `400ms` | High-attention moments, modals |

### Easing Tokens (from `tokens.css`)

| Token | Value | Usage |
|-------|-------|-------|
| `--ease-standard` | `cubic-bezier(0.2, 0.75, 0.25, 1)` | Most components |
| `--ease-out` | `cubic-bezier(0, 0, 0.2, 1)` | Elements settling to rest |
| `--ease-in` | `cubic-bezier(0.4, 0, 1, 1)` | Elements starting from rest |
| `--ease-bounce` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Confirmation moments only |

### Color Tokens

All motion uses the semantic color system from `tokens.css`. Brand motion uses `--color-brand` (#f0a8c4), accent uses `--color-accent` (#e8d0ff).

---

## 2. Motion Classes

Every motion earns its place by answering "where did that come from?" → page-enter / card-enter.

### Page-Level Motions

| Class | Animation | Duration | Easing |
|-------|-----------|----------|--------|
| `.motion-page-enter` | `motion-fade-in` + `motion-rise` | `--motion-standard` + `--motion-relaxed` | `--motion-ease-standard` + `--motion-ease-entrance` |
| `.motion-page-exit` | `motion-fade-out` | `--motion-quick` | `--motion-ease-exit` |

### Section Motions

| Class | Animation | Duration | Easing |
|-------|-----------|----------|--------|
| `.motion-section-enter` | `motion-rise` | `--motion-relaxed` | `--motion-ease-entrance` |

### Card Entrance

| Class | Animation | Duration | Easing |
|-------|-----------|----------|--------|
| `.motion-card-enter` | `motion-card-enter` keyframe | `--motion-relaxed` | `--motion-ease-entrance` |

### Stagger Children

Children carry `.motion-card-enter`; this class only assigns delay:

```css
.motion-stagger > * {
  animation-delay: calc(var(--motion-stagger-step) * var(--motion-stagger-index, 0));
}
--motion-stagger-step: 45ms;
```

### Button Press

```css
.motion-press {
  transition: transform var(--motion-quick) var(--motion-ease-standard);
}
.motion-press:active:not(:disabled) {
  transform: scale(0.97);
}
```

### Focus

```css
.motion-focus {
  transition: border-color var(--motion-quick) var(--motion-ease-standard),
              box-shadow var(--motion-quick) var(--motion-ease-standard);
}
.motion-focus:focus-visible,
.motion-focus:focus {
  border-color: var(--color-brand);
  box-shadow: 0 0 0 3px var(--color-brand-muted);
}
```

### Status: Success / Error / Loading

```css
.motion-success {
  animation: motion-check var(--motion-relaxed) var(--motion-ease-emphasis) both;
}
.motion-error {
  animation: motion-shake var(--motion-standard) var(--motion-ease-standard) both;
}
.motion-loading {
  animation: motion-breathe 1.4s var(--motion-ease-standard) infinite;
}
.motion-spin {
  animation: motion-spin 900ms linear infinite;
}
```

### Data Reveals

```css
.motion-chart-reveal {
  animation: motion-chart-reveal var(--motion-relaxed) var(--motion-ease-entrance) both;
  transform-origin: bottom center;
}
.motion-insight-reveal {
  animation: motion-insight-reveal var(--motion-relaxed) var(--motion-ease-entrance) both;
}
.motion-cycle-sweep {
  animation: motion-cycle-sweep var(--motion-relaxed) var(--motion-ease-entrance) both;
  transform-origin: center;
}
```

### Navigation Indicator

```css
.motion-nav-indicator {
  transition: transform var(--motion-relaxed) var(--motion-ease-entrance),
              opacity var(--motion-quick) var(--motion-ease-standard);
}
```

### Tooltip / Popover

```css
.motion-tooltip-enter {
  animation: motion-popover-in var(--motion-quick) var(--motion-ease-entrance) both;
}
.motion-popover-enter {
  animation: motion-popover-in var(--motion-quick) var(--motion-ease-entrance) both;
}
```

### Toast

```css
.motion-toast-enter {
  animation: motion-toast-in var(--motion-relaxed) var(--motion-ease-entrance) both;
}
```

---

## 3. Reduced Motion (Mandatory — `prefers-reduced-motion: reduce`)

All continuous motion stops. Entrance animations collapse to plain fade. The `motion.css` and `tokens.css` already define the reduced-motion media query — components must use the motion classes.

### What Collapses to Fade

| Class | Reduced-Motion Fallback |
|-------|------------------------|
| `.motion-stagger > *` | `animation-delay: 0ms !important` |
| `.motion-card-enter`, `.motion-section-enter`, `.motion-modal-panel-enter`, `.motion-drawer-enter`, `.motion-toast-enter` | `animation-name: motion-fade-in`, `animation-duration: var(--motion-quick)`, `transform: none` |
| `.motion-cycle-sweep`, `.motion-chart-reveal`, `.motion-spin`, `.motion-loading`, `.motion-skeleton` | `animation: none` |
| `.motion-skeleton` (still visible) | `background: var(--color-surface-soft)` (flat tone) |
| `.motion-error`, `.motion-success` | `animation-duration: var(--motion-quick)` |

### What Stops Completely

- Spinners, shimmers, breathing loops
- Continuous rotations (`motion-spin`)
- Skeleton shimmer loops (`motion-skeleton-sweep`)
- Breathe animations (`motion-breathe`)

A still skeleton must not read as broken — hold a flat tone via `--color-surface-soft`.

---

## 4. Component-Specific Animation Plans

### A. Hero Entrance Sequence

**Elements and order:**

1. **Background** — subtle ambient drift (3D organic form only, no CSS animation)
2. **Organic visual** — slow pulse/float (3.js mesh motion, 20s cycle)
3. **Headline** — `motion-page-enter` fade+rise
4. **Supporting copy** — `motion-section-enter` rise
5. **CTA button** — `motion-fast` press-scale on hover

**Framer Motion variants (HomeClient.tsx):**

```tsx
const heroVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      type: "spring",
      duration: 1.2,
      delayChildren: 0.2,
      staggerChildren: 0.15,
    },
  },
};

// Background/organic: 3.js only, no Framer Motion animation on the canvas itself
// Headline fades in sequentially via AnimatePresence
// CTA has hover-scale: [1, 1.02] with --duration-fast
```

### B. Ambient 3D Movement (Anatomy3D)

The 3D organ form uses Three.js with these motions:

- **Organ positions**: Static positions from `ORGAN_POSITIONS_3D` — no continuous rotation
- **On-select highlight**: Scale briefly from `1` to `1.15` and back ( `--duration-fast`, `--ease-out` )
- **OrbitControls**: `enableZoom`, `enablePan` — user-driven only
- **Lights**: Static — `ambientLight intensity={0.6}`, `pointLight position={[5, 5, 5]}`

**No CSS animation loops** on the 3D canvas. All motion is user-driven or one-shot on interaction.

### C. Section Transition Animations

Using `AnimatePresence` with `motion.div`:

```tsx
<AnimatePresence>
  <motion.div
    key={activeView}
    initial={false}
    animate={{ opacity: 1, x: 0 }}
    exit={{ opacity: 0, x: activeView === "dashboard" ? -20 : 20 }}
    transition={{ type: "spring", duration: 0.3 }}
    className="flex-1 min-w-0 p-page-lg max-w-content mx-auto w-full"
  >
    {/* Section content */}
  </motion.div>
</AnimatePresence>
```

Each section uses `.motion-section-enter` for enter, and exit animates out directionally based on which view is leaving.

### D. Hover Interactions

| Element | Interaction | Variant |
|---------|------------|---------|
| **Navigation items** | `whileHover: { opacity: [0.7, 1] }`, `whileTap: { opacity: [0.9, 1] }` | `scaleIn` |
| **CTA buttons** | `whileHover: { scale: [1, 1.02] }`, `whileTap: { scale: [0.98, 1] }` | `hoverScale` |
| **Metric tiles** | `whileHover: hoverScale.hover`, `whileTap: hoverScale.tap` | `hoverScale` |
| **Insight cards** | `whileHover: hoverScale.hover`, `whileTap: hoverScale.tap` | `hoverScale` |
| **Section dividers** | `whileHover: { scale: [1, 1.01] }`, `whileTap: { scale: [0.99, 1] }` | `scaleIn` |

All hover interactions use `--duration-fast` (120ms) and `--ease-standard`.

### E. Reduced Motion Fallback Per Component

| Component | Full Motion | Reduced-Motion Fallback |
|-----------|------------|------------------------|
| **Hero entrance** | Spring-staggered fade+in | All collapse to `opacity: 1` instantly (0ms) via `.motion-page-enter` media query |
| **Metric tiles** | `scaleIn` on enter + `hoverScale` | Enter: `fade-in` `--duration-fast`; Hover: `transform: none` |
| **Insight cards** | `scaleIn` on enter + `hoverScale` | Same as metric tiles |
| **Trend cards** | `fadeIn("up")` enter | `fade-in` `--duration-fast` only |
| **3D anatomy** | On-select scale highlight | Scale highlight becomes instant opacity change |
| **Navigation** | `whileHover` opacity/scale | Opacity changes become `transform: none`, hover styling via color only |
| **CTA button** | `whileHover` scale | Scale becomes `transform: none`, color change remains |

---

## 5. Performance Considerations

### General Rules

1. **No layout shaking** — all animations use `transform` and `opacity` only. Never animate `width`, `height`, `top`, `left`, or `margin` directly.
2. **No uncontrolled loops** — every `animation-direction: infinite` has a clear purpose and respects `prefers-reduced-motion`.
3. **GPU minimal** — only transform/opacity changes trigger GPU compositing. Color/background animations are CPU-side when possible.
4. **Stagger Children** — use `animation-delay` with `calc()` (as in `.motion-stagger`), not JS timeouts.
5. **Framer Motion `type: "spring"`** — use sparingly; prefer `type: "tween"` for predictable performance.

### Framer Motion Specifics

- `whileHover` / `whileTap` — only animate `transform` and `opacity`. Do not animate `backgroundColor` directly in the variant; use CSS `.hover-glow-brand` transition instead.
- `AnimatePresence` — always set `initial={false}` when the child already has its own `initial`/`animate` variants to avoid double-animation.
- `variants` — define once, reuse across the component. Do not inline variants that duplicate existing tokens.
- `className` motion classes — prefer the CSS `.motion-*` classes from `motion.css` over inline Framer Motion `variants` when the animation is static (entrance/exit).

### Three.js (Anatomy3D)

- Keep shader complexity low — no post-processing, no raycasting on every frame.
- `OrbitControls` with sensible `minDistance={2}`, `maxDistance={10}` to prevent the camera from getting too close and causing render overhead.
- One `Canvas` mount — never conditionally render/ dispose the Canvas.
- Use `meshStandardMaterial` with simple colors — no textures, no env maps.

---

## 6. Event Listener Cleanup Plan

Framer Motion automatically cleans up `whileHover` / `whileTap` listeners on unmount. For any custom event listeners:

| Listener | Cleanup |
|----------|---------|
| `window.addEventListener("resize", ...)` | In `useEffect` return: `window.removeEventListener("resize", handler)` |
| `document.addEventListener("click", ...)` | Same pattern — save handler reference, remove on unmount |
| `IntersectionObserver` | `observer.disconnect()` in cleanup function |
| `useFrame` (Three.js) | Return `() => { animationFrame.unsubscribe() }` or clear the interval |

**HomeClient.tsx pattern** (already present):

```tsx
useEffect(() => {
  let mounted = true;
  if (session) {
    loadHealthOverview().then(() => {
      if (!mounted) return;
    });
  }
  return () => { mounted = false; };
}, [session, loadHealthOverview]);
```

Apply the same `mounted` guard pattern to any animation-related effects.

---

## 7. Storyboard: Hero Entrance Sequence

| Time | Element | Animation |
|------|---------|-----------|
| `t+0ms` | Page mount | `prefers-reduced-motion` check; if reduce, skip all motion |
| `t+50ms` | Background organic form | 3.js init; static placement; no animation on first render |
| `t+100ms` | Headline | `motion-fade-in` + `motion-rise` from `--duration-normal` (`200ms`), `--ease-entrance` |
| `t+150ms` | Supporting copy | `motion-section-enter` rise, 150ms delay after headline |
| `t+200ms` | CTA button | Enter with `--duration-fast` (`120ms`), hover-scale `[1, 1.02]` |
| `t+250ms` | Ambient pulse (3.js) | Optional one-shot pulse on CTA focus, not continuous loop |
| `t+300ms` | Full page settled | All elements at rest; reduced motion: all collapsed to instant fade |

**Reduced-motion variant:** All of the above occurs at `0ms` (instant fade-in), no rise, no stagger, no pulse.

---

## Implementation Checklist

- [x] Motion tokens defined in `frontend/tokens.css` and `frontend/app/motion.css`
- [x] Reduced-motion media query in both `tokens.css` and `motion.css`
- [x] All motion classes use `transform` + `opacity` only
- [x] No layout-animate properties (`width`, `height`, `top`, `left`, `margin`)
- [x] `prefers-reduced-motion: reduce` collapses continuous motion, fades entrance
- [x] Hover interactions use `--duration-fast` and `--ease-standard`
- [x] 3D anatomy: no continuous CSS loops; on-select scale only
- [x] Framer Motion variants reused from token system
- [x] `AnimatePresence` with `initial={false}` where child has own variants
- [x] Event listener cleanup via `useEffect` return guards
- [x] Storyboard documented with reduced-motion variant