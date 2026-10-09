const POLL_MS = 20;
const RMS_THRESHOLD = 0.012;
const SILENCE_BEFORE_ONSET_MS = 250;

/**
 * Detects when the agent's audio actually becomes audible in this browser, by measuring
 * the energy of the received track (not LiveKit's server-side speaker detection).
 */
export class AgentAudioMonitor {
  private context: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private analyser: AnalyserNode | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private lastSoundAt = Number.NEGATIVE_INFINITY;

  constructor(private readonly onOnset: (atMs: number) => void) {}

  attach(track: MediaStreamTrack): void {
    this.detach();
    this.context ??= new AudioContext();
    void this.context.resume();
    this.analyser = this.context.createAnalyser();
    this.analyser.fftSize = 512;
    this.source = this.context.createMediaStreamSource(new MediaStream([track]));
    this.source.connect(this.analyser);
    const buffer = new Float32Array(this.analyser.fftSize);
    this.timer = setInterval(() => this.poll(buffer), POLL_MS);
  }

  detach(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.source?.disconnect();
    this.source = null;
    this.analyser = null;
  }

  dispose(): void {
    this.detach();
    void this.context?.close();
    this.context = null;
  }

  private poll(buffer: Float32Array<ArrayBuffer>): void {
    if (!this.analyser) return;
    this.analyser.getFloatTimeDomainData(buffer);
    let sum = 0;
    for (const sample of buffer) sum += sample * sample;
    const rms = Math.sqrt(sum / buffer.length);
    const now = performance.now();
    if (rms < RMS_THRESHOLD) return;
    if (now - this.lastSoundAt > SILENCE_BEFORE_ONSET_MS) this.onOnset(now);
    this.lastSoundAt = now;
  }
}
