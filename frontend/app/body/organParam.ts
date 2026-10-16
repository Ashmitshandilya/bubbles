/** `/body?organ=brain` opens the map with that area selected. Only a plain id is accepted; the map ignores ids it does not have. */
export function organFromSearch(search: string): string | null {
  const v = new URLSearchParams(search).get("organ");
  return v && /^[a-z_]{1,40}$/.test(v) ? v : null;
}
