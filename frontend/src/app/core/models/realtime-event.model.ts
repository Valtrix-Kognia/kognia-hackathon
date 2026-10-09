import { CountResult, DatasetOverview, GroupResult, IpsDetail, SearchResult } from './ips.model';

export const EVENTS_TOPIC = 'kognia.events';

export type EventType =
  | 'session.started'
  | 'session.ended'
  | 'agent.listening'
  | 'agent.thinking'
  | 'agent.speaking'
  | 'transcript.partial'
  | 'transcript.final'
  | 'speaker.identified'
  | 'emotion.analyzed'
  | 'ips.query.started'
  | 'ips.query.completed'
  | 'ips.query.failed'
  | 'error.occurred'
  | 'metrics.turn'
  | 'turn.decision'
  | 'turn.mode'
  | 'metrics.client'
  | 'agent.interrupted';

export interface RealtimeEvent<T = unknown> {
  type: EventType;
  session_id: string;
  seq: number;
  turn_id?: string | null;
  emitted_at: string;
  payload: T;
}

export type SpeakerRole = 'user' | 'agent';

export interface TranscriptSegment {
  id: string;
  session_id: string;
  role: SpeakerRole;
  speaker_id: string;
  speaker_label: string;
  text: string;
  start_ms: number;
  end_ms: number;
  is_final: boolean;
  interrupted: boolean;
  overlap_suspected?: boolean;
  timestamp: string;
}

export type Sentiment = 'positivo' | 'neutral' | 'negativo';
export type Emotion = 'alegria' | 'tristeza' | 'enojo' | 'miedo' | 'sorpresa' | 'asco' | 'neutral';

export interface EmotionAnalysis {
  segment_id: string;
  session_id: string;
  speaker_label: string;
  status: 'ok' | 'texto_insuficiente' | 'error';
  sentiment: Sentiment | null;
  sentiment_score: number | null;
  emotion: Emotion | null;
  emotion_score: number | null;
  low_confidence: boolean;
  model: string;
  source: 'texto';
  analyzed_at: string;
}

export interface SpeakerIdentified {
  speaker_id: string;
  speaker_label: string;
  segment_id: string;
}

export type IpsToolName =
  | 'count_ips'
  | 'group_ips'
  | 'search_ips'
  | 'get_ips_details'
  | 'get_dataset_overview';

export type IpsToolResult = CountResult | GroupResult | SearchResult | IpsDetail | DatasetOverview;

export interface IpsQueryEvent {
  query_id: string;
  tool: IpsToolName;
  arguments: Record<string, unknown>;
  result?: IpsToolResult | null;
  message?: string;
}

export interface SessionStartedPayload {
  stt: string;
  llm: string;
  tts: string;
  diarization: boolean;
  noise_model?: string;
  turn_mode?: TurnMode;
}

export type TurnMode = 'open' | 'wake_word';

export interface TurnDecisionPayload {
  turn_id: string;
  action: 'respond' | 'ignore' | 'ask_repeat' | 'hold' | 'listen';
  reason: string;
  mode: TurnMode;
  activation: 'confirmada' | 'probable' | 'ambigua' | 'ninguna';
  text: string;
  merged_from: string[];
}

export interface TurnLatencyPayload {
  turn_id: string;
  decision: string;
  outcome: string;
  marks_ms: Record<string, number>;
  socrata_http_ms: number;
  events: { name: string; at_ms: number }[];
  stages_ms: Partial<
    Record<
      | 'transcription_delay'
      | 'end_of_turn_delay'
      | 'llm_node_ttft'
      | 'llm_node_ttfs'
      | 'tts_node_ttfb'
      | 'first_audio'
      | 'e2e_latency',
      number
    >
  >;
  tools: { tool: string; duration_ms: number; cache_hit: boolean }[];
  socrata_ms: number;
  summary: {
    turns: number;
    e2e_p50_ms: number | null;
    e2e_p95_ms: number | null;
    first_audio_p50_ms: number | null;
    first_audio_p95_ms: number | null;
    browser_audible_p50_ms: number | null;
    browser_audible_p95_ms: number | null;
  };
}

export interface PlaybackMeasurement {
  turn_id: string;
  action: TurnDecisionPayload['action'];
  status: 'medido' | 'reemplazado';
  decision_to_audible_ms?: number;
  speaking_event_to_audible_ms?: number;
}

export interface ErrorPayload {
  source: string;
  recoverable: boolean;
  message: string;
}
