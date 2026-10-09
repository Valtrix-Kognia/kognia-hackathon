export interface QueryMetadata {
  dataset_id: string;
  source: string;
  queried_at: string;
  filters: Record<string, string>;
  limitations: string[];
}

export interface CountResult {
  registros: number;
  prestadores: number;
  sedes: number;
  metadata: QueryMetadata;
}

export interface GroupBucket {
  label: string;
  value: number;
}

export interface GroupResult {
  dimension: string;
  metric: 'registros' | 'prestadores' | 'sedes' | 'capacidad_instalada';
  metric_description: string;
  buckets: GroupBucket[];
  metadata: QueryMetadata;
}

export interface IpsSite {
  codigo_sede: string;
  nombre_sede: string;
  codigo_prestador: string;
  nombre_prestador: string;
  departamento: string;
  municipio: string;
  naturaleza: string | null;
  nivel_atencion: string | null;
  direccion: string | null;
  telefono: string | null;
}

export interface SearchResult {
  total_sedes: number;
  page: number;
  page_size: number;
  items: IpsSite[];
  metadata: QueryMetadata;
}

export interface CapacityLine {
  grupo: string;
  descripcion: string;
  cantidad: number;
}

export interface IpsDetail {
  site: IpsSite;
  capacidades: CapacityLine[];
  fecha_corte: string | null;
  metadata: QueryMetadata;
}

export interface DatasetOverview {
  name: string;
  description: string;
  attribution: string | null;
  rows_updated_at: string | null;
  totals: CountResult;
  fields: Record<string, string>;
  limitations: string[];
}
