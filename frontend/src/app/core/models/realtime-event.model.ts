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
  | 'error.occurred';

export interface RealtimeEvent<T = unknown> {
  type: EventType;
  session_id: string;
  seq: number;
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
}

export interface ErrorPayload {
  source: string;
  recoverable: boolean;
  message: string;
}
