import { Injectable, NgZone, OnDestroy, inject, signal } from '@angular/core';
import {
  DisconnectReason,
  LocalAudioTrack,
  MediaDeviceFailure,
  RemoteAudioTrack,
  RemoteTrack,
  Room,
  RoomEvent,
  Track,
} from 'livekit-client';
import { EVENTS_TOPIC, PlaybackMeasurement, RealtimeEvent, TurnMode } from '../models/realtime-event.model';
import { AgentAudioMonitor } from './agent-audio-monitor';
import { ConnectionState, MicState, VoiceSession } from '../models/voice-session.model';
import { ConversationStore } from './conversation-store.service';
import { SessionApiService } from './session-api.service';
import { ToastService } from './toast.service';

const AGENT_TRANSCRIPTION_TOPIC = 'lk.transcription';
const TURN_MODE_ATTRIBUTE = 'kognia.turn_mode';
const CLIENT_METRICS_TOPIC = 'kognia.client_metrics';
/** The dashboard always uses explicit activation ("Kognia, …") for the shared microphone. */
const ACTIVATION_MODE: TurnMode = 'wake_word';

/**
 * Shared-microphone capture. Noise suppression runs once, server side (ai-coustics QUAIL_L,
 * which keeps every voice); the browser's own suppressor is disabled so distant speakers are
 * not attenuated twice. Echo cancellation stays on so the agent's voice is not re-captured,
 * and AGC helps people sitting farther from the microphone.
 */
const SHARED_MIC_CAPTURE = { echoCancellation: true, noiseSuppression: false, autoGainControl: true, channelCount: 1 };

/** Owns the LiveKit room lifecycle: connect, microphone, agent audio, events and cleanup. */
@Injectable({ providedIn: 'root' })
export class VoiceRoomService implements OnDestroy {
  private readonly api = inject(SessionApiService);
  private readonly store = inject(ConversationStore);
  private readonly toasts = inject(ToastService);
  private readonly zone = inject(NgZone);

  private room: Room | null = null;
  private session: VoiceSession | null = null;
  private userInitiatedDisconnect = false;
  private readonly audioElements = new Set<HTMLMediaElement>();
  private readonly onDeviceChange = () => void this.refreshDevices();
  private readonly audioMonitor = new AgentAudioMonitor((at) => this.store.markAgentAudible(at));

  constructor() {
    this.store.setMeasurementSink((m) => void this.sendMeasurement(m));
  }

  readonly connection = signal<ConnectionState>('idle');
  readonly mic = signal<MicState>('off');
  readonly audioBlocked = signal(false);
  readonly microphones = signal<MediaDeviceInfo[]>([]);
  readonly activeMicId = signal<string | null>(null);
  readonly localTrack = signal<MediaStreamTrack | null>(null);
  readonly agentTrack = signal<MediaStreamTrack | null>(null);
  readonly sessionId = signal<string | null>(null);
  readonly expiresAt = signal<string | null>(null);

  async start(): Promise<void> {
    if (this.connection() === 'connecting' || this.connection() === 'connected') return;
    this.connection.set('connecting');
    try {
      this.session = await this.api.create();
    } catch {
      this.connection.set('error');
      this.toasts.show('error', 'No fue posible crear la sesión de voz. Verifica tu conexión e inténtalo de nuevo.');
      return;
    }
    this.store.reset(this.session.session_id);
    await this.connect(this.session);
  }

  async reconnect(): Promise<void> {
    if (!this.session) {
      await this.start();
      return;
    }
    this.connection.set('connecting');
    try {
      this.session = await this.api.refresh(this.session.session_id);
    } catch {
      this.connection.set('error');
      this.toasts.show('error', 'No fue posible renovar la sesión. Inicia una nueva.');
      return;
    }
    await this.connect(this.session);
  }

  async stop(): Promise<void> {
    this.userInitiatedDisconnect = true;
    await this.teardown();
    this.connection.set('idle');
    this.mic.set('off');
    this.store.setOffline();
  }

  async newSession(): Promise<void> {
    await this.stop();
    this.store.reset(null);
    this.session = null;
    this.sessionId.set(null);
    await this.start();
  }

  async toggleMute(): Promise<void> {
    const room = this.room;
    if (!room) return;
    const enable = this.mic() !== 'on';
    await this.setMicrophone(room, enable);
  }

  async selectMicrophone(deviceId: string): Promise<void> {
    if (!this.room) return;
    const ok = await this.room.switchActiveDevice('audioinput', deviceId);
    if (ok) {
      this.activeMicId.set(deviceId);
      this.syncLocalTrack();
    } else {
      this.toasts.show('warning', 'No se pudo cambiar de micrófono.');
    }
  }

  /** Send a typed request; the agent's room input handles the 'lk.chat' topic. */
  async sendText(text: string): Promise<boolean> {
    const room = this.room;
    const clean = text.trim();
    if (!room || room.state !== 'connected' || !clean) return false;
    try {
      await room.localParticipant.sendText(clean, { topic: 'lk.chat' });
      this.store.addTypedMessage(clean);
      return true;
    } catch {
      this.toasts.show('error', 'No se pudo enviar el mensaje escrito.');
      return false;
    }
  }

  async resumeAudio(): Promise<void> {
    await this.room?.startAudio();
    this.audioBlocked.set(!(this.room?.canPlaybackAudio ?? true));
  }

  ngOnDestroy(): void {
    this.audioMonitor.dispose();
    void this.teardown();
  }

  private async connect(session: VoiceSession): Promise<void> {
    await this.teardown();
    this.userInitiatedDisconnect = false;
    this.sessionId.set(session.session_id);
    this.expiresAt.set(session.expires_at);
    const room = new Room({
      adaptiveStream: true,
      dynacast: true,
      audioCaptureDefaults: SHARED_MIC_CAPTURE,
    });
    this.room = room;
    this.bindRoomEvents(room);
    try {
      await room.connect(session.livekit_url, session.token);
    } catch {
      this.connection.set('error');
      this.toasts.show('error', 'No fue posible conectar con el servidor de voz.');
      await this.teardown();
      return;
    }
    this.connection.set('connected');
    this.toasts.show(
      'success',
      'Conectado. Empieza tus preguntas con “Kognia…”.',
      4000,
    );
    await room.localParticipant.setAttributes({ [TURN_MODE_ATTRIBUTE]: ACTIVATION_MODE }).catch(() => undefined);
    await this.setMicrophone(room, true);
    await this.resumeAudio();
    navigator.mediaDevices?.addEventListener('devicechange', this.onDeviceChange);
    await this.refreshDevices();
  }

  private async setMicrophone(room: Room, enabled: boolean): Promise<void> {
    if (enabled) this.mic.set('requesting');
    try {
      await room.localParticipant.setMicrophoneEnabled(enabled);
      this.mic.set(enabled ? 'on' : 'muted');
      this.syncLocalTrack();
    } catch (error) {
      const failure = MediaDeviceFailure.getFailure(error);
      if (failure === MediaDeviceFailure.PermissionDenied) {
        this.mic.set('denied');
        this.toasts.show('error', 'Permiso de micrófono denegado. Habilítalo en la configuración del navegador.', 8000);
      } else {
        this.mic.set('unavailable');
        this.toasts.show('error', 'No se encontró un micrófono disponible.', 8000);
      }
    }
  }

  private syncLocalTrack(): void {
    const publication = this.room?.localParticipant.getTrackPublication(Track.Source.Microphone);
    const track = publication?.track as LocalAudioTrack | undefined;
    this.localTrack.set(track?.mediaStreamTrack ?? null);
  }

  private bindRoomEvents(room: Room): void {
    const run = (fn: () => void) => this.zone.run(fn);

    room
      .on(RoomEvent.Reconnecting, () => run(() => this.connection.set('reconnecting')))
      .on(RoomEvent.Reconnected, () =>
        run(() => {
          this.connection.set('connected');
          this.toasts.show('success', 'Conexión restablecida.', 3000);
        }),
      )
      .on(RoomEvent.Disconnected, (reason?: DisconnectReason) =>
        run(() => {
          if (this.userInitiatedDisconnect) return;
          this.connection.set('disconnected');
          this.store.setOffline();
          const expired = reason === DisconnectReason.JOIN_FAILURE || reason === DisconnectReason.STATE_MISMATCH;
          this.toasts.show(
            'warning',
            expired ? 'La sesión expiró o no es válida. Reconecta para continuar.' : 'Se perdió la conexión de voz.',
            8000,
          );
        }),
      )
      .on(RoomEvent.TrackSubscribed, (track: RemoteTrack) =>
        run(() => {
          if (track.kind !== Track.Kind.Audio) return;
          const element = (track as RemoteAudioTrack).attach();
          element.style.display = 'none';
          document.body.appendChild(element);
          this.audioElements.add(element);
          this.agentTrack.set(track.mediaStreamTrack);
          this.audioMonitor.attach(track.mediaStreamTrack);
        }),
      )
      .on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) =>
        run(() => {
          track.detach().forEach((el) => {
            el.remove();
            this.audioElements.delete(el);
          });
          if (this.agentTrack() === track.mediaStreamTrack) this.agentTrack.set(null);
        }),
      )
      .on(RoomEvent.AudioPlaybackStatusChanged, () => run(() => this.audioBlocked.set(!room.canPlaybackAudio)))
      .on(RoomEvent.MediaDevicesError, (error: Error) =>
        run(() => {
          const failure = MediaDeviceFailure.getFailure(error);
          this.mic.set(failure === MediaDeviceFailure.PermissionDenied ? 'denied' : 'unavailable');
        }),
      )
      .on(RoomEvent.ActiveDeviceChanged, (kind: MediaDeviceKind, deviceId: string) =>
        run(() => {
          if (kind === 'audioinput') this.activeMicId.set(deviceId);
        }),
      );

    room.registerTextStreamHandler(EVENTS_TOPIC, async (reader) => {
      const text = await reader.readAll();
      try {
        const event = JSON.parse(text) as RealtimeEvent;
        run(() => this.store.apply(event));
      } catch {
        console.warn('Evento con formato inválido descartado');
      }
    });

    room.registerTextStreamHandler(AGENT_TRANSCRIPTION_TOPIC, async (reader, participant) => {
      if (participant.identity === room.localParticipant.identity) return;
      let text = '';
      for await (const chunk of reader) {
        text += chunk;
        const current = text;
        run(() => this.store.applyAgentLiveText(reader.info.id, current));
      }
    });
  }

  private async sendMeasurement(measurement: PlaybackMeasurement): Promise<void> {
    const room = this.room;
    if (!room || room.state !== 'connected') return;
    const payload = new TextEncoder().encode(JSON.stringify(measurement));
    try {
      await room.localParticipant.publishData(payload, { reliable: true, topic: CLIENT_METRICS_TOPIC });
    } catch {
      console.warn('No se pudo enviar la medición de reproducción');
    }
  }

  private async refreshDevices(): Promise<void> {
    try {
      const devices = await Room.getLocalDevices('audioinput', false);
      this.microphones.set(devices.filter((d) => d.deviceId));
      if (this.room) {
        this.activeMicId.set(this.room.getActiveDevice('audioinput') ?? null);
      }
    } catch {
      this.microphones.set([]);
    }
  }

  private async teardown(): Promise<void> {
    navigator.mediaDevices?.removeEventListener('devicechange', this.onDeviceChange);
    const room = this.room;
    this.room = null;
    if (room) {
      room.unregisterTextStreamHandler(EVENTS_TOPIC);
      room.unregisterTextStreamHandler(AGENT_TRANSCRIPTION_TOPIC);
      room.removeAllListeners();
      await room.disconnect();
    }
    this.audioMonitor.detach();
    this.audioElements.forEach((el) => el.remove());
    this.audioElements.clear();
    this.localTrack.set(null);
    this.agentTrack.set(null);
  }
}
