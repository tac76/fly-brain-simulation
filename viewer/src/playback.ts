// Playback clock over recording frames (50 fps simulated time).

export class Playback {
  frame = 0;
  speed = 0.5;
  playing = false;

  constructor(
    readonly nFrames: number,
    readonly fps = 50,
  ) {}

  get last(): number {
    return Math.max(this.nFrames - 1, 0);
  }

  play(): void {
    if (this.frame >= this.last) this.frame = 0;
    this.playing = true;
  }

  pause(): void {
    this.playing = false;
  }

  seek(frame: number): void {
    this.frame = Math.min(Math.max(frame, 0), this.last);
  }

  /** Advance by wall-clock seconds; returns the new fractional frame. */
  tick(dtWallS: number): number {
    if (!this.playing) return this.frame;
    this.frame += dtWallS * this.fps * this.speed;
    if (this.frame >= this.last) {
      this.frame = this.last;
      this.playing = false;
    }
    return this.frame;
  }
}
