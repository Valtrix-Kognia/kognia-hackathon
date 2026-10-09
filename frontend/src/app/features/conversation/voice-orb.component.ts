import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  input,
  output,
  viewChild,
} from '@angular/core';

const BARS = 48;
const SPEAKING_RMS = 0.02;
const MIC_COLOR = '34, 211, 238';
const AGENT_COLOR = '139, 92, 246';

interface Channel {
  source: MediaStreamAudioSourceNode;
  analyser: AnalyserNode;
  buffer: Uint8Array<ArrayBuffer>;
  level: number;
}

/**
 * Voice visualizer driven by real audio: inner radial bars = microphone spectrum,
 * outer halo = agent output energy. Animates only while a session has live tracks.
 */
@Component({
  selector: 'app-voice-orb',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<canvas #canvas class="mx-auto block aspect-square w-full max-w-[17rem]" aria-hidden="true"></canvas>`,
})
export class VoiceOrbComponent {
  readonly micTrack = input<MediaStreamTrack | null>(null);
  readonly agentTrack = input<MediaStreamTrack | null>(null);
  readonly active = input(false);
  readonly tone = input<'idle' | 'busy' | 'error'>('idle');
  readonly userSpeaking = output<boolean>();

  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private context: AudioContext | null = null;
  private mic: Channel | null = null;
  private agent: Channel | null = null;
  private frame = 0;
  private speaking = false;
  private phase = 0;

  constructor() {
    effect(() => {
      this.mic = this.rewire(this.mic, this.micTrack(), 256);
      this.agent = this.rewire(this.agent, this.agentTrack(), 128);
      this.tone();
      this.restart();
    });
    effect(() => {
      if (!this.active()) this.setSpeaking(false);
      this.restart();
    });
    inject(DestroyRef).onDestroy(() => {
      cancelAnimationFrame(this.frame);
      this.mic?.source.disconnect();
      this.agent?.source.disconnect();
      void this.context?.close();
    });
  }

  private rewire(current: Channel | null, track: MediaStreamTrack | null, fftSize: number): Channel | null {
    if (current && track && current.source.mediaStream.getAudioTracks()[0] === track) return current;
    current?.source.disconnect();
    if (!track) return null;
    this.context ??= new AudioContext();
    void this.context.resume();
    const analyser = this.context.createAnalyser();
    analyser.fftSize = fftSize;
    analyser.smoothingTimeConstant = 0.8;
    const source = this.context.createMediaStreamSource(new MediaStream([track]));
    source.connect(analyser);
    return { source, analyser, buffer: new Uint8Array(analyser.frequencyBinCount), level: 0 };
  }

  private restart(): void {
    cancelAnimationFrame(this.frame);
    this.draw();
  }

  private sample(channel: Channel | null): number {
    if (!channel) return 0;
    channel.analyser.getByteTimeDomainData(channel.buffer);
    let sum = 0;
    for (const v of channel.buffer) {
      const centered = (v - 128) / 128;
      sum += centered * centered;
    }
    const rms = Math.sqrt(sum / channel.buffer.length);
    channel.level = channel.level * 0.7 + rms * 0.3;
    return channel.level;
  }

  private setSpeaking(value: boolean): void {
    if (value !== this.speaking) {
      this.speaking = value;
      this.userSpeaking.emit(value);
    }
  }

  private draw(): void {
    const canvas = this.canvas().nativeElement;
    const ratio = window.devicePixelRatio || 1;
    const size = canvas.clientWidth * ratio;
    if (canvas.width !== size) {
      canvas.width = size;
      canvas.height = size;
    }
    const ctx = canvas.getContext('2d');
    if (!ctx || !size) return;
    const live = this.active() && (!!this.mic || !!this.agent);
    const micLevel = live ? this.sample(this.mic) : 0;
    const agentLevel = live ? this.sample(this.agent) : 0;
    this.setSpeaking(live && micLevel > SPEAKING_RMS);

    const c = size / 2;
    const base = size * 0.24;
    ctx.clearRect(0, 0, size, size);

    const halo = base * (1.15 + Math.min(agentLevel * 6, 0.9));
    const gradient = ctx.createRadialGradient(c, c, base * 0.6, c, c, halo * 1.25);
    const errorTone = this.tone() === 'error';
    const haloColor = errorTone ? '239, 68, 68' : AGENT_COLOR;
    gradient.addColorStop(0, `rgba(${haloColor}, ${0.25 + Math.min(agentLevel * 4, 0.5)})`);
    gradient.addColorStop(1, `rgba(${haloColor}, 0)`);
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(c, c, halo * 1.25, 0, Math.PI * 2);
    ctx.fill();

    if (this.mic && live) {
      this.mic.analyser.getByteFrequencyData(this.mic.buffer);
      for (let i = 0; i < BARS; i++) {
        const v = this.mic.buffer[Math.floor((i / BARS) * this.mic.buffer.length * 0.6)] / 255;
        const angle = (i / BARS) * Math.PI * 2 - Math.PI / 2;
        const inner = base * 1.05;
        const outer = inner + 4 * ratio + v * base * 0.55;
        ctx.strokeStyle = `rgba(${MIC_COLOR}, ${0.25 + v * 0.75})`;
        ctx.lineWidth = 2.5 * ratio;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(c + Math.cos(angle) * inner, c + Math.sin(angle) * inner);
        ctx.lineTo(c + Math.cos(angle) * outer, c + Math.sin(angle) * outer);
        ctx.stroke();
      }
    }

    if (this.tone() === 'busy' && live) this.phase = (this.phase + 0.04) % (Math.PI * 2);
    const core = ctx.createLinearGradient(c - base, c - base, c + base, c + base);
    core.addColorStop(0, live ? '#3b82f6' : '#22324f');
    core.addColorStop(1, live ? '#8b5cf6' : '#192740');
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(c, c, base * (1 + agentLevel * 0.8), 0, Math.PI * 2);
    ctx.fill();
    if (this.tone() === 'busy' && live) {
      ctx.strokeStyle = 'rgba(241, 245, 249, 0.8)';
      ctx.lineWidth = 2 * ratio;
      ctx.beginPath();
      ctx.arc(c, c, base * 0.62, this.phase, this.phase + Math.PI * 0.6);
      ctx.stroke();
    }

    if (live) this.frame = requestAnimationFrame(() => this.draw());
  }
}
