// Geometry for the "soap pop" save feedback: a few droplets flying out from a centre point.
// Fixed, not random, so server and client render the same thing and the pop looks the same every time.

export interface Droplet {
  /** Where the droplet ends up, in px from the centre. */
  x: number;
  y: number;
  /** Diameter in px. */
  size: number;
  /** Animation delay in ms. */
  delay: number;
}

const round1 = (n: number) => Math.round(n * 10) / 10;

/**
 * `count` droplets spread evenly around a circle, starting straight up. Every other droplet stops short and is
 * smaller, which reads as spray instead of a ring of identical dots.
 */
export function burstDroplets(count = 8, radius = 28): Droplet[] {
  const n = Math.max(0, Math.floor(count));
  return Array.from({ length: n }, (_, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    const near = i % 2 === 1;
    const reach = near ? radius * 0.65 : radius;
    return {
      x: round1(Math.cos(angle) * reach),
      y: round1(Math.sin(angle) * reach),
      size: near ? 4 : 6,
      delay: (i % 3) * 25,
    };
  });
}
