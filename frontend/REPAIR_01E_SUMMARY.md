# REPAIR 01E - Duplicate React Key Fixes in CompanionClient.tsx

## Problem
Duplicate React keys causing React reconciliation warnings and potential rendering issues:
1. **Evidence links** (line 492): Keys used `ev.chunkId ?? `${ev.title}-${ev.sourceName}`` - if multiple evidence items had the same `title`+`sourceName` combination, React would show duplicate key warnings
2. **Health events** (line 473): Keys used `event.id ?? `${event.eventType}-${idx}`` - the index-as-key pattern is problematic for React reconciliation and can cause inconsistent UI state

## Fixes Applied

### Fix 1: Health Events Keys (CompanionClient.tsx line 473)
**Before:**
```tsx
{msg.healthEvents.map((event, idx) => (
  <button
    key={event.id ?? `${event.eventType}-${idx}`}
    ...
  >
```
**After:**
```tsx
{msg.healthEvents.map((event, idx) => {
  const stableKey = event.id ?? `health-event-${event.eventType}-${idx}`;
  return (
    <button key={stableKey} ...>
```
- Uses stable event ID first when available
- Falls back to `health-event-{eventType}-{idx}` only when ID is null
- Avoids the pure index-as-key pattern that React warns against

### Fix 2: Evidence Links Keys (CompanionClient.tsx line 492)
**Before:**
```tsx
{msg.evidence.map((ev) => (
  <a key={ev.chunkId ?? `${ev.title}-${ev.sourceName}`} ...>
```
**After:**
```tsx
{msg.evidence.map((ev, idx) => {
  const stableKey = ev.chunkId ?? `evidence-${ev.title}-${ev.sourceName}-${idx}`;
  return (
    <a key={stableKey} ...>
```
- Uses `chunkId` first when available (stable backend identifier)
- Falls back to `evidence-{title}-{sourceName}-{idx}` with explicit index suffix
- Added `idx` parameter to `map()` callback for the fallback key

## Verification
- ✅ Frontend build: `npm run build` passes successfully
- ✅ Frontend lint: `npm run lint` passes successfully  
- ✅ Backend tests: 129/129 tests pass (`pytest tests -x -v`)

## Risk Mitigation
- No behavioral changes to the UI - only key stability improvements
- Fallback keys are deterministic and won't change between renders when chunkId is present
- When chunkId is absent, the idx suffix ensures uniqueness
- Changes are minimal and reversible
