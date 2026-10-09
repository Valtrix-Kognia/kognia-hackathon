import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom, timeout } from 'rxjs';
import { API_CONFIG } from '../config/api-config';
import { VoiceSession } from '../models/voice-session.model';

@Injectable({ providedIn: 'root' })
export class SessionApiService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(API_CONFIG);

  create(): Promise<VoiceSession> {
    return firstValueFrom(
      this.http.post<VoiceSession>(`${this.config.baseUrl}/api/v1/sessions`, {}).pipe(timeout(15000)),
    );
  }

  refresh(sessionId: string): Promise<VoiceSession> {
    return firstValueFrom(
      this.http
        .post<VoiceSession>(
          `${this.config.baseUrl}/api/v1/sessions/${encodeURIComponent(sessionId)}/token`,
          {},
        )
        .pipe(timeout(15000)),
    );
  }
}
