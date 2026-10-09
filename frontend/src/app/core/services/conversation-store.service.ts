import { Injectable, computed, signal } from '@angular/core';
import {
  EmotionAnalysis,
  ErrorPayload,
  IpsQueryEvent,
  RealtimeEvent,
  SessionStartedPayload,
  SpeakerIdentified,
  TranscriptSegment,
  TurnDecisionPayload,
  TurnLatencyPayload,
  TurnMode,
} from '../models/realtime-event.model';
import { AgentActivity } from '../models/voice-session.model';

export type QueryStatus = 'running' | 'completed' | 'failed';

export interface TrackedQuery {
  queryId: string;
  tool: IpsQueryEvent['tool'];
  arguments: Record<string, unknown>;
  status: QueryStatus;
  result: IpsQueryEvent['result'];
  message?: string;
  startedAt: string;
  question?: string;
}

export interface AgentLiveText {
  id: string;
  text: string;
}

/**
 * Single source of truth for one voice session's dashboard state.
 * Events from other sessions or older than what was already applied are ignored.
 */
@Injectable({ providedIn: 'root' })
export class ConversationStore {
  private readonly lastSeqByKey = new Map<string, number>();

  readonly sessionId = signal<string | null>(null);
  readonly sessionInfo = signal<SessionStartedPayload | null>(null);
  readonly agentState = signal<AgentActivity>('offline');
  readonly segmentsById = signal<ReadonlyMap<string, TranscriptSegment>>(new Map());
  readonly speakers = signal<ReadonlyMap<string, string>>(new Map());
  readonly emotions = signal<EmotionAnalysis[]>([]);
  readonly queries = signal<TrackedQuery[]>([]);
  readonly lastError = signal<ErrorPayload | null>(null);
  readonly agentLive = signal<AgentLiveText | null>(null);
  readonly turnMode = signal<TurnMode>('wake_word');
  readonly lastDecision = signal<TurnDecisionPayload | null>(null);
  readonly decisionCounts = signal<Record<TurnDecisionPayload['action'], number>>({
    respond: 0,
    ignore: 0,
    ask_repeat: 0,
  });
  readonly latencyTurns = signal<TurnLatencyPayload[]>([]);
  /** Browser-side: turn decision received -> agent audible (LiveKit active speaker). */
  readonly browserPlaybackMs = signal<number[]>([]);
  private pendingResponseAt: number | null = null;
  private readonly decisionLog = signal<TurnDecisionPayload[]>([]);

  readonly segments = computed(() =>
    [...this.segmentsById().values()].sort((a, b) => a.start_ms - b.start_ms || a.end_ms - b.end_ms),
  );
  readonly runningQueries = computed(() => this.queries().filter((q) => q.status === 'running').length);
  readonly activity = computed<AgentActivity>(() =>
    this.runningQueries() > 0 && this.agentState() !== 'offline' ? 'querying' : this.agentState(),
  );
  readonly latestQuery = computed<TrackedQuery | null>(() => this.queries()[0] ?? null);
  readonly emotionBySegment = computed(
    () => new Map(this.emotions().map((e) => [e.segment_id, e] as const)),
  );

  reset(sessionId: string | null): void {
    this.lastSeqByKey.clear();
    this.sessionId.set(sessionId);
    this.sessionInfo.set(null);
    this.agentState.set(sessionId ? 'waiting' : 'offline');
    this.segmentsById.set(new Map());
    this.speakers.set(new Map());
    this.emotions.set([]);
    this.queries.set([]);
    this.lastError.set(null);
    this.agentLive.set(null);
    this.lastDecision.set(null);
    this.decisionLog.set([]);
    this.decisionCounts.set({ respond: 0, ignore: 0, ask_repeat: 0 });
    this.latencyTurns.set([]);
    this.browserPlaybackMs.set([]);
    this.pendingResponseAt = null;
  }

  setOffline(): void {
    this.agentState.set('offline');
    this.agentLive.set(null);
  }

  /** Session snapshot used by the manual multi-speaker test protocol (bench/score_session.py). */
  exportSnapshot(): Record<string, unknown> {
    return {
      session_id: this.sessionId(),
      exported_at: new Date().toISOString(),
      session_info: this.sessionInfo(),
      turn_mode: this.turnMode(),
      segments: this.segments().filter((s) => s.is_final),
      speakers: Object.fromEntries(this.speakers()),
      decisions: this.decisionLog(),
      emotions: this.emotions(),
      latency_turns: this.latencyTurns(),
      browser_playback_ms: this.browserPlaybackMs(),
    };
  }

  markAgentAudible(nowMs: number): void {
    if (this.pendingResponseAt === null) return;
    const elapsed = Math.round(nowMs - this.pendingResponseAt);
    this.pendingResponseAt = null;
    this.browserPlaybackMs.update((list) => [...list, elapsed].slice(-50));
  }

  applyAgentLiveText(id: string, text: string): void {
    this.agentLive.set(text.trim() ? { id, text } : null);
  }

  apply(event: RealtimeEvent): boolean {
    if (!this.sessionId() || event.session_id !== this.sessionId()) {
      return false;
    }
    switch (event.type) {
      case 'session.started': {
        const info = event.payload as SessionStartedPayload;
        this.sessionInfo.set(info);
        if (info.turn_mode) this.turnMode.set(info.turn_mode);
        return true;
      }
      case 'turn.mode':
        this.turnMode.set((event.payload as { mode: TurnMode }).mode);
        return true;
      case 'turn.decision': {
        const decision = event.payload as TurnDecisionPayload;
        this.lastDecision.set(decision);
        this.decisionLog.update((list) => [...list, decision]);
        this.decisionCounts.update((c) => ({ ...c, [decision.action]: c[decision.action] + 1 }));
        this.pendingResponseAt = decision.action === 'ignore' ? null : performance.now();
        return true;
      }
      case 'metrics.turn':
        this.latencyTurns.update((list) => [...list, event.payload as TurnLatencyPayload].slice(-50));
        return true;
      case 'session.ended':
        this.setOffline();
        return true;
      case 'agent.listening':
      case 'agent.thinking':
      case 'agent.speaking':
        if (this.isStale('agent.state', event.seq)) return false;
        this.agentState.set(event.type.slice('agent.'.length) as AgentActivity);
        return true;
      case 'transcript.partial':
      case 'transcript.final':
        return this.applySegment(event as RealtimeEvent<TranscriptSegment>);
      case 'speaker.identified': {
        const payload = event.payload as SpeakerIdentified;
        this.speakers.update((m) => new Map(m).set(payload.speaker_id, payload.speaker_label));
        return true;
      }
      case 'emotion.analyzed': {
        const analysis = event.payload as EmotionAnalysis;
        this.emotions.update((list) => [...list.filter((e) => e.segment_id !== analysis.segment_id), analysis]);
        return true;
      }
      case 'ips.query.started':
      case 'ips.query.completed':
      case 'ips.query.failed':
        return this.applyQuery(event as RealtimeEvent<IpsQueryEvent>);
      case 'error.occurred':
        this.lastError.set(event.payload as ErrorPayload);
        return true;
      default:
        return false;
    }
  }

  private isStale(key: string, seq: number): boolean {
    const last = this.lastSeqByKey.get(key) ?? 0;
    if (seq <= last) return true;
    this.lastSeqByKey.set(key, seq);
    return false;
  }

  private applySegment(event: RealtimeEvent<TranscriptSegment>): boolean {
    const segment = event.payload;
    const existing = this.segmentsById().get(segment.id);
    if (existing?.is_final && !segment.is_final) return false;
    if (this.isStale(`segment:${segment.id}`, event.seq) && !segment.is_final) return false;
    this.segmentsById.update((m) => new Map(m).set(segment.id, segment));
    if (segment.role === 'agent') {
      this.agentLive.set(null);
    }
    return true;
  }

  private applyQuery(event: RealtimeEvent<IpsQueryEvent>): boolean {
    const payload = event.payload;
    if (this.isStale(`query:${payload.query_id}`, event.seq)) return false;
    const status: QueryStatus =
      event.type === 'ips.query.started' ? 'running' : event.type === 'ips.query.completed' ? 'completed' : 'failed';
    this.queries.update((list) => {
      const current = list.find((q) => q.queryId === payload.query_id);
      const updated: TrackedQuery = {
        queryId: payload.query_id,
        tool: payload.tool,
        arguments: payload.arguments,
        status,
        result: payload.result ?? current?.result ?? null,
        message: payload.message,
        startedAt: current?.startedAt ?? event.emitted_at,
        question: current?.question ?? this.lastUserText(),
      };
      return [updated, ...list.filter((q) => q.queryId !== payload.query_id)].slice(0, 20);
    });
    return true;
  }

  private lastUserText(): string | undefined {
    const users = this.segments().filter((s) => s.role === 'user' && s.is_final);
    return users.at(-1)?.text;
  }
}
