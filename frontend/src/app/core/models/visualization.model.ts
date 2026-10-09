import { QueryMetadata } from './ips.model';
import { IpsToolName } from './realtime-event.model';

/** Visualization kinds the dashboard can render. line_chart is reserved for data with a
 * temporal or sequential dimension; dataset s2ru-bqt6 has none, so the builder never emits it. */
export type VisualizationKind =
  | 'metric'
  | 'table'
  | 'bar_chart'
  | 'horizontal_bar'
  | 'donut_chart'
  | 'line_chart'
  | 'colombia_map';

export type MapMetric = 'sedes' | 'registros';

export interface VisualizationProvenance {
  queryId: string;
  tool: IpsToolName;
  metadata: QueryMetadata;
}

interface BaseSpec {
  id: string;
  kind: VisualizationKind;
  title: string;
  description: string;
  /** Unit of analysis, always explicit (registros, sedes, prestadores...). */
  unit: string;
  provenance: VisualizationProvenance;
}

export interface MetricItem {
  label: string;
  value: number;
  unit: string;
  emphasis?: boolean;
}

export interface MetricSpec extends BaseSpec {
  kind: 'metric';
  items: MetricItem[];
}

export interface CategoryDatum {
  label: string;
  value: number;
}

export interface CategoryChartSpec extends BaseSpec {
  kind: 'horizontal_bar' | 'bar_chart' | 'donut_chart';
  data: CategoryDatum[];
}

export interface LineChartSpec extends BaseSpec {
  kind: 'line_chart';
  points: { x: number; y: number }[];
}

export interface TableSpec extends BaseSpec {
  kind: 'table';
  columns: { key: string; label: string; numeric?: boolean }[];
  rows: Record<string, string | number | null>[];
}

export interface ColombiaMapSpec extends BaseSpec {
  kind: 'colombia_map';
  metric: MapMetric;
  data: CategoryDatum[];
}

export type VisualizationSpec = MetricSpec | CategoryChartSpec | LineChartSpec | TableSpec | ColombiaMapSpec;
