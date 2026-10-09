export interface VoiceSession {
  session_id: string;
  room_name: string;
  participant_identity: string;
  livekit_url: string;
  token: string;
  expires_at: string;
}

export type ConnectionState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'error';

export type MicState = 'off' | 'requesting' | 'on' | 'muted' | 'denied' | 'unavailable';

export type AgentActivity =
  | 'offline'
  | 'waiting'
  | 'listening'
  | 'thinking'
  | 'querying'
  | 'speaking';
