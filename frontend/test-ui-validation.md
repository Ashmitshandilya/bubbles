# UI Validation Checklist — Organ Tracker

## Visual & Interaction Tests
- [ ] Skeleton renders (head, spine, ribs, pelvis, limbs all visible)
- [ ] 9 organ nodes positioned correctly on skeleton
- [ ] Nodes show correct status colors (green/orange/red/dashed)
- [ ] Node hover effect (scale 1.15x, glow)
- [ ] Node click selects (ring animation + glowing effect)
- [ ] Selected node shows right panel with details
- [ ] Right panel shows: name, status badge, score, completeness bar, signals, limitations
- [ ] Petal animations float smoothly (not jittery)
- [ ] Sparkle dots pulse smoothly
- [ ] Hero text renders with gradient background
- [ ] Summary stats display correctly (systems with data, need attention, watch, total)
- [ ] Loading skeleton shows pulsing placeholders
- [ ] Error state shows alert with retry button
- [ ] Demo state shows UnicornMark + sign-in CTA (unauthenticated)
- [ ] Mobile: stacks to single column, no horizontal scroll
- [ ] Keyboard: Tab navigates nodes, Enter selects
- [ ] Focus ring visible on all interactive elements (brand color)
- [ ] prefers-reduced-motion: all animations disabled

## Data States
- [ ] No data: all nodes show dashed outline
- [ ] Partial data: mix of colored dots and dashed outlines
- [ ] Full data: all 9 organs colored by status
- [ ] Completeness bar: width reflects 0-100%
- [ ] Confidence display: shows actual percentage
- [ ] Signal factors: display with direction (risk/protective)

## Integration Points
- [ ] /health page: OrganTracker renders with all states
- [ ] /dashboard: OrganPanel renders when activeView === "dashboard"
- [ ] Refresh button updates organ data
- [ ] Same skeleton + nodes on both pages
- [ ] No null renders; always shows some state
- [ ] Petal/sparkle decorations use global CSS (not scoped)

## Accessibility
- [ ] ARIA labels on nodes (descriptive text)
- [ ] Semantic HTML (buttons, sections, headings)
- [ ] Color contrast WCAG AA (4.5:1 minimum)
- [ ] Keyboard focus visible
- [ ] Screen reader: proper heading hierarchy
- [ ] No flashing (animations respects prefers-reduced-motion)

## Unicorn Branding
- [ ] Navigation sidebar: UnicornMark (36px)
- [ ] Navigation header: UnicornMark (36px)
- [ ] Home loading: UnicornMark (80px)
- [ ] Dashboard loading: UnicornMark (80px)
- [ ] Health loading: UnicornMark (80px)
- [ ] Organ demo: UnicornMark (48px, no sparkles)
- [ ] All "C" icons replaced with unicorn
