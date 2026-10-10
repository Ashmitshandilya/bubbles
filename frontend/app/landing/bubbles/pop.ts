/**
 * Droplets thrown out when a soap bubble pops: a fixed pool in typed arrays, recycled in a ring, so a pop
 * never allocates. Positions are viewport px. Sound and vibration are intentionally absent: the plan keeps
 * both off until a visitor can switch them on, and there is no such control yet.
 */

export const MAX_DROPS = 18;
export const DROP_LIFE_S = 0.7;
/** px/s squared, downward: a soap droplet drifts, it does not fall like a stone */
const GRAVITY = 70;

export class Droplets {
  readonly x = new Float32Array(MAX_DROPS);
  readonly y = new Float32Array(MAX_DROPS);
  readonly r = new Float32Array(MAX_DROPS);
  /** 1 just thrown .. 0 gone */
  readonly life = new Float32Array(MAX_DROPS);
  private readonly vx = new Float32Array(MAX_DROPS);
  private readonly vy = new Float32Array(MAX_DROPS);
  private cursor = 0;

  /** Throw `n` droplets from a bubble of radius `radius` at (x, y). `rand` is injectable for tests. */
  burst(x: number, y: number, radius: number, rand: () => number = Math.random, n = 10) {
    for (let k = 0; k < n; k += 1) {
      const i = this.cursor;
      this.cursor = (this.cursor + 1) % MAX_DROPS;
      const angle = (k / n) * Math.PI * 2 + rand() * 0.6;
      const speed = (60 + rand() * 120) * Math.min(1.6, 0.6 + radius / 90);
      this.x[i] = x + Math.cos(angle) * radius * 0.7;
      this.y[i] = y + Math.sin(angle) * radius * 0.7;
      this.vx[i] = Math.cos(angle) * speed;
      this.vy[i] = Math.sin(angle) * speed;
      this.r[i] = 2.5 + rand() * 3.5;
      this.life[i] = 1;
    }
  }

  step(dt: number) {
    const fade = dt / DROP_LIFE_S;
    for (let i = 0; i < MAX_DROPS; i += 1) {
      if (this.life[i] <= 0) continue;
      this.life[i] = Math.max(0, this.life[i] - fade);
      this.vx[i] *= Math.exp(-2.2 * dt);
      this.vy[i] = this.vy[i] * Math.exp(-2.2 * dt) + GRAVITY * dt;
      this.x[i] += this.vx[i] * dt;
      this.y[i] += this.vy[i] * dt;
    }
  }

  get alive() {
    let n = 0;
    for (let i = 0; i < MAX_DROPS; i += 1) if (this.life[i] > 0) n += 1;
    return n;
  }
}
