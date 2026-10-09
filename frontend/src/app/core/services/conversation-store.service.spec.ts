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

  it('measures browser playback per turn and marks superseded turns', () => {
    const sent: unknown[] = [];
    store.setMeasurementSink((m) => sent.push(m));
    store.apply(event('turn.mode', 1, { mode: 'open' }));
    expect(store.turnMode()).toBe('open');
    const decision = (seq: number, turn_id: string, action: string) =>
      event('turn.decision', seq, { turn_id, action, reason: 'x', mode: 'open', activation: 'ninguna', text: '', merged_from: [] });
    store.apply(decision(2, 't1', 'ignore'));
    store.markAgentAudible(performance.now() + 10);
    expect(store.playback()).toEqual([]);
    store.apply(decision(3, 't2', 'respond'));
    store.apply(decision(4, 't3', 'respond'));
    store.apply({ ...event('agent.speaking', 5, {}), turn_id: 't3' });
    store.markAgentAudible(performance.now() + 1500);
    const statuses = store.playback().map((m) => [m.turn_id, m.status]);
    expect(statuses).toEqual([['t2', 'reemplazado'], ['t3', 'medido']]);
    expect(store.playback()[1].speaking_event_to_audible_ms).toBeGreaterThan(0);
    expect(sent.length).toBe(2);
    expect(store.decisionCounts().respond).toBe(2);
  });

  it('resets everything on a new session', () => {
    store.apply(event('transcript.final', 1, segment({ is_final: true })));
    store.reset('room-c');
    expect(store.segments()).toEqual([]);
    expect(store.queries()).toEqual([]);
    expect(store.sessionId()).toBe('room-c');
  });
});
