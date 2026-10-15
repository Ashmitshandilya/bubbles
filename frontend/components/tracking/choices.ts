// Pure helpers for chip groups. A multi-select group keeps its picks in one comma-separated string, which is also what the
// tracker API accepts, so the form state stays a plain string for every field type.

export function parseChoices(value: string): string[] {
  return value.split(",").map((part) => part.trim()).filter(Boolean);
}

export function isChosen(value: string, option: string, multi: boolean): boolean {
  return multi ? parseChoices(value).includes(option) : value === option;
}

/** The value after tapping `option`: single-select replaces (or clears when tapped again), multi-select adds or removes. */
export function toggleChoice(value: string, option: string, multi: boolean, allowDeselect = true): string {
  if (!multi) return value === option && allowDeselect ? "" : option;
  const picked = parseChoices(value);
  return (picked.includes(option) ? picked.filter((item) => item !== option) : [...picked, option]).join(",");
}

/** "dry, red" shown as "Dry, Red eyes"-style labels; an option it does not know is shown as typed. */
export function choiceLabels(value: string, options: readonly { value: string; label: string }[]): string {
  return parseChoices(value).map((item) => options.find((o) => o.value === item)?.label ?? item).join(", ");
}
