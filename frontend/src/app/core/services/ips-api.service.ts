import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, shareReplay, timeout } from 'rxjs';
import { API_CONFIG } from '../config/api-config';
import { CountResult, GroupResult } from '../models/ips.model';

type Params = Record<string, string | number | undefined | null>;

/**
 * Read-only access to the Kognia API (which queries datos.gov.co). Identical requests share
 * one HTTP call and are cached for the session, so map exploration never repeats queries.
 */
@Injectable({ providedIn: 'root' })
export class IpsApiService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(API_CONFIG);
  private readonly cache = new Map<string, Observable<unknown>>();

  groupByDepartment(metric: 'sedes' | 'registros' | 'prestadores', filters: Params = {}): Observable<GroupResult> {
    return this.get<GroupResult>('/api/v1/ips/group', { dimension: 'departamento', metric, top_n: 40, ...filters });
  }

  groupBy(dimension: string, metric: string, filters: Params = {}): Observable<GroupResult> {
    return this.get<GroupResult>('/api/v1/ips/group', { dimension, metric, top_n: 10, ...filters });
  }

  count(filters: Params): Observable<CountResult> {
    return this.get<CountResult>('/api/v1/ips/count', filters);
  }

  private get<T>(path: string, raw: Params): Observable<T> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(raw).sort(([a], [b]) => a.localeCompare(b))) {
      if (value !== undefined && value !== null && value !== '') params = params.set(key, String(value));
    }
    const key = `${path}?${params.toString()}`;
    let request = this.cache.get(key) as Observable<T> | undefined;
    if (!request) {
      request = this.http
        .get<T>(`${this.config.baseUrl}${path}`, { params })
        .pipe(timeout(20000), shareReplay({ bufferSize: 1, refCount: false }));
      this.cache.set(key, request);
      request.subscribe({ error: () => this.cache.delete(key) });
    }
    return request;
  }
}
