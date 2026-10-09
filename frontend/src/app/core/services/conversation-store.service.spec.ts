import { TestBed } from '@angular/core/testing';
import { EventType, RealtimeEvent, TranscriptSegment } from '../models/realtime-event.model';
import { ConversationStore } from './conversation-store.service';

function event<T>(type: EventType, seq: number, payload: T, session = 'room-a'): RealtimeEvent<T> {
  return { type, seq, session_id: session, emitted_at: new Date().toISOString(), payload };
}

function segment(overrides: Partial<TranscriptSegment>): TranscriptSegment {
  return {
    id: 'u-1',
    session_id: 'room-a',
    role: 'user',
    speaker_id: '0',
    speaker_label: 'Hablante 1',
    text: 'hola',
    start_ms: 0,
    end_ms: 100,
    is_final: false,
    interrupted: false,
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}

describe('ConversationStore', () => {
  let store: ConversationStore;

  beforeEach(() => {
    store = TestBed.inject(ConversationStore);
    store.reset('room-a');
  });

  it('ignores events from another session', () => {
    expect(store.apply(event('agent.speaking', 1, {}, 'room-b'))).toBe(false);
    expect(store.agentState()).toBe('waiting');
  });

  it('replaces a partial with its final segment and never regresses to partial', () => {
    store.apply(event('transcript.partial', 1, segment({ text: 'cuán' })));
    store.apply(event('transcript.final', 3, segment({ text: '¿Cuántas IPS hay?', is_final: true })));
    store.apply(event('transcript.partial', 2, segment({ text: 'cuántas' })));
    expect(store.segments().length).toBe(1);
    expect(store.segments()[0].text).toBe('¿Cuántas IPS hay?');
    expect(store.segments()[0].is_final).toBe(true);
  });

  it('keeps several speakers ordered by start time', () => {
    store.apply(event('transcript.final', 1, segment({ id: 'u-2', speaker_label: 'Hablante 2', start_ms: 900, is_final: true })));
    store.apply(event('transcript.final', 2, segment({ id: 'u-1', start_ms: 100, is_final: true })));
    expect(store.segments().map((s) => s.speaker_label)).toEqual(['Hablante 1', 'Hablante 2']);
  });

  it('applies agent state only when newer', () => {
    store.apply(event('agent.thinking', 5, {}));
    store.apply(event('agent.listening', 4, {}));
    expect(store.agentState()).toBe('thinking');
  });

  it('shows querying while an IPS query runs and records its result', () => {
    store.apply(event('agent.thinking', 1, {}));
    store.apply(event('ips.query.started', 2, { query_id: 'q1', tool: 'count_ips', arguments: {} }));
    expect(store.activity()).toBe('querying');
    store.apply(event('ips.query.completed', 3, { query_id: 'q1', tool: 'count_ips', arguments: {}, result: null }));
    expect(store.activity()).toBe('thinking');
    expect(store.latestQuery()?.status).toBe('completed');
  });

  it('tracks turn decisions, mode and browser playback latency', () => {
    store.apply(event('turn.mode', 1, { mode: 'open' }));
    expect(store.turnMode()).toBe('open');
    store.apply(event('turn.decision', 2, { action: 'ignore', reason: 'muletilla', mode: 'open', text: 'ok' }));
    store.markAgentAudible(1000);
    expect(store.browserPlaybackMs()).toEqual([]);
    store.apply(event('turn.decision', 3, { action: 'respond', reason: 'conversacion_abierta', mode: 'open', text: '¿Cuántas?' }));
    store.markAgentAudible(performance.now() + 1500);
    expect(store.browserPlaybackMs().length).toBe(1);
    expect(store.decisionCounts()).toEqual({ respond: 1, ignore: 1, ask_repeat: 0 });
  });

  it('resets everything on a new session', () => {
    store.apply(event('transcript.final', 1, segment({ is_final: true })));
    store.reset('room-c');
    expect(store.segments()).toEqual([]);
    expect(store.queries()).toEqual([]);
    expect(store.sessionId()).toBe('room-c');
  });
});
