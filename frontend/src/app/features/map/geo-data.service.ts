import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, shareReplay } from 'rxjs';

export interface DepartmentFeature {
  type: 'Feature';
  properties: { name: string; iso: string };
  geometry: { type: 'MultiPolygon'; coordinates: number[][][][] };
}

export interface DepartmentCollection {
  type: 'FeatureCollection';
  attribution: string;
  features: DepartmentFeature[];
}

/** Loads the departmental GeoJSON once per session (static asset, ~180 kB gzip). */
@Injectable({ providedIn: 'root' })
export class GeoDataService {
  private readonly http = inject(HttpClient);
  readonly departments$: Observable<DepartmentCollection> = this.http
    .get<DepartmentCollection>('geo/colombia-departamentos.geojson')
    .pipe(shareReplay({ bufferSize: 1, refCount: false }));
}
