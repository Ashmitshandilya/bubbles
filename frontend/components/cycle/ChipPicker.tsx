"use client";

// Searchable feelings/symptoms picker: selected pills on top, live search, grouped accordions, and own-words chips.

import { useId, useState } from "react";
import { addCustom, MAX_CUSTOM_LENGTH, searchChips, selectedChips, selectedCounts, toggleId } from "../../app/lib/cycle-chips";
import type { ChipGroup } from "../../app/lib/cycle-types";
import { INPUT, RemovablePill, TagInput, ToggleChip } from "./fields";

export function ChipPicker({
  groups, selected, custom, onSelected, onCustom,
}: {
  groups: ChipGroup[];
  selected: string[];
  custom: string[];
  onSelected: (ids: string[]) => void;
  onCustom: (list: string[]) => void;
}) {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const matches = searchChips(groups, query);
  const picked = selectedChips(groups, selected);
  const counts = selectedCounts(groups, selected);
  const searching = query.trim().length > 0;

  return (
    <div className="space-y-4">
      <div aria-live="polite">
        <p className="m-0 text-body-sm font-extrabold text-ink">Selected ({picked.length + custom.length})</p>
        {picked.length + custom.length === 0 ? (
          <p className="m-0 mt-1 text-body-sm text-muted">Nothing picked yet. Skip anything that does not apply.</p>
        ) : (
          <ul className="m-0 mt-2 flex list-none flex-wrap gap-2 p-0">
            {picked.map((p) => (
              <li key={p.id}><RemovablePill label={p.label} onRemove={() => onSelected(toggleId(selected, p.id))} /></li>
            ))}
            {custom.map((c) => (
              <li key={`custom-${c}`}><RemovablePill label={c} onRemove={() => onCustom(custom.filter((x) => x !== c))} /></li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <label htmlFor={searchId} className="block text-body-sm font-extrabold text-ink">Search feelings and symptoms</label>
        <input
          id={searchId}
          type="search"
          value={query}
          autoComplete="off"
          placeholder="Try “cramps”, “tired” or “spots”"
          onChange={(e) => setQuery(e.target.value)}
          className={`${INPUT} mt-2`}
        />
        <p role="status" className="m-0 mt-1 text-body-sm text-muted">
          {searching ? (matches.length ? `${matches.length} match${matches.length === 1 ? "" : "es"}` : "No match. You can add it in your own words below.") : ""}
        </p>
      </div>

      {searching ? (
        <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
          {matches.map((chip) => (
            <li key={chip.id}>
              <ToggleChip pressed={selected.includes(chip.id)} onClick={() => onSelected(toggleId(selected, chip.id))}>{chip.label}</ToggleChip>
            </li>
          ))}
        </ul>
      ) : (
        <div className="space-y-2">
          {groups.map((group, i) => (
            <details key={group.id} open={i === 0} className="rounded-2xl border border-line bg-surface">
              <summary className="flex min-h-[44px] cursor-pointer items-center justify-between gap-2 px-4 py-2 text-body font-extrabold text-ink">
                <span>{group.label}</span>
                {counts[group.id] > 0 && <span className="rounded-full bg-tint-pink px-2.5 py-0.5 text-chip font-extrabold text-bubbles-pink-deep">{counts[group.id]} selected</span>}
              </summary>
              <ul className="m-0 flex list-none flex-wrap gap-2 p-4 pt-1">
                {group.chips.map((chip) => (
                  <li key={chip.id}>
                    <ToggleChip pressed={selected.includes(chip.id)} onClick={() => onSelected(toggleId(selected, chip.id))}>{chip.label}</ToggleChip>
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </div>
      )}

      <TagInput
        label="Something else? Add it in your own words"
        tags={custom}
        onChange={onCustom}
        add={addCustom}
        maxLength={MAX_CUSTOM_LENGTH}
        placeholder="e.g. sore knees"
      />
    </div>
  );
}
