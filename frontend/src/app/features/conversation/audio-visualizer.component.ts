import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  input,
  viewChild,
} from '@angular/core';

const BAR_COUNT = 32;

/** Real-time level bars from a MediaStreamTrack via Web Audio AnalyserNode. */
@Component({
  selector: 'app-audio-visualizer',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<canvas #canvas class="h-24 w-full" aria-hidden="true"></canvas>`,
})
export class AudioVisualizerComponent {
  readonly track = input<MediaStreamTrack | null>(null);
  readonly color = input('#3b63dd');

  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private context: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private analyser: AnalyserNode | null = null;
  private frame = 0;

  constructor() {
    effect(() => this.connect(this.track()));
    inject(DestroyRef).onDestroy(() => {
      cancelAnimationFrame(this.frame);
      this.disconnect();
      void this.context?.close();
    });
  }

  private connect(track: MediaStreamTrack | null): void {
    this.disconnect();
    if (track) {
      this.context ??= new AudioContext();
      void this.context.resume();
      this.analyser = this.context.createAnalyser();
      this.analyser.fftSize = 128;
      this.analyser.smoothingTimeConstant = 0.75;
      this.source = this.context.createMediaStreamSource(new MediaStream([track]));
      this.source.connect(this.analyser);
    }
    cancelAnimationFrame(this.frame);
    this.draw();
  }

  private disconnect(): void {
    this.source?.disconnect();
    this.source = null;
    this.analyser = null;
  }

  private draw(): void {
    const canvas = this.canvas().nativeElement;
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth * ratio;
    const height = canvas.clientHeight * ratio;
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const data = new Uint8Array(this.analyser?.frequencyBinCount ?? BAR_COUNT);
    this.analyser?.getByteFrequencyData(data);
    ctx.clearRect(0, 0, width, height);
    const gap = 4 * ratio;
    const barWidth = (width - gap * (BAR_COUNT - 1)) / BAR_COUNT;
    ctx.fillStyle = this.color();
    for (let i = 0; i < BAR_COUNT; i++) {
      const value = this.analyser ? data[Math.floor((i / BAR_COUNT) * data.length * 0.7)] / 255 : 0;
      const barHeight = Math.max(4 * ratio, value * height);
      const x = i * (barWidth + gap);
      const y = (height - barHeight) / 2;
      ctx.globalAlpha = this.analyser ? 0.35 + value * 0.65 : 0.2;
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, barHeight, barWidth / 2);
      ctx.fill();
    }
    if (this.analyser) {
      this.frame = requestAnimationFrame(() => this.draw());
    }
  }
}
