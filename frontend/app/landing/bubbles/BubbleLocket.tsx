/**
 * The locket: a soap bubble that holds Bubbles in chapters 2 to 8. Pure CSS (landing.css, `.cw-locket`), so it
 * costs nothing on any tier. It lives inside the host wrapper, which already follows the 3D anchor, and shows
 * when BubblesHost sets `data-locket="1"` on that wrapper.
 */
export function BubbleLocket() {
  return (
    <span className="cw-locket" aria-hidden="true">
      <i className="cw-locket-win" />
      <i className="cw-locket-dot" />
    </span>
  );
}
