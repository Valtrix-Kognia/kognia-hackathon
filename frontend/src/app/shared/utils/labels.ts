import { Emotion, IpsToolName, Sentiment } from '../../core/models/realtime-event.model';

export const TOOL_LABELS: Record<IpsToolName, string> = {
  count_ips: 'Conteo de IPS',
  group_ips: 'Agrupación y ranking',
  search_ips: 'Búsqueda de sedes',
  get_ips_details: 'Detalle de sede',
  get_dataset_overview: 'Descripción de la fuente',
};

export const FILTER_LABELS: Record<string, string> = {
  departamento: 'Departamento',
  municipio: 'Municipio',
  naturaleza: 'Naturaleza',
  nivel_atencion: 'Nivel de atención',
  grupo_capacidad: 'Grupo de capacidad',
  nombre_contiene: 'Nombre contiene',
};

export const DIMENSION_LABELS: Record<string, string> = {
  departamento: 'Departamento',
  municipio: 'Municipio',
  naturaleza: 'Naturaleza',
  num_nivel_atencion: 'Nivel de atención',
  nom_grupo_capacidad: 'Grupo de capacidad',
  nom_descripcion_capacidad: 'Tipo de capacidad',
};

export const SENTIMENT_META: Record<Sentiment, { label: string; dot: string; bar: string; text: string }> = {
  positivo: { label: 'Positivo', dot: 'bg-emerald-500', bar: 'bg-emerald-500', text: 'text-emerald-300' },
  neutral: { label: 'Neutral', dot: 'bg-slate-400', bar: 'bg-slate-400', text: 'text-slate-300' },
  negativo: { label: 'Negativo', dot: 'bg-rose-500', bar: 'bg-rose-500', text: 'text-rose-300' },
};

export const EMOTION_META: Record<Emotion, { label: string; chip: string }> = {
  alegria: { label: 'Alegría', chip: 'bg-amber-400/15 text-amber-200 ring-1 ring-amber-400/30' },
  tristeza: { label: 'Tristeza', chip: 'bg-sky-400/15 text-sky-200 ring-1 ring-sky-400/30' },
  enojo: { label: 'Enojo', chip: 'bg-rose-400/15 text-rose-200 ring-1 ring-rose-400/30' },
  miedo: { label: 'Miedo', chip: 'bg-violet-400/15 text-violet-200 ring-1 ring-violet-400/30' },
  sorpresa: { label: 'Sorpresa', chip: 'bg-fuchsia-400/15 text-fuchsia-200 ring-1 ring-fuchsia-400/30' },
  asco: { label: 'Asco', chip: 'bg-lime-400/15 text-lime-200 ring-1 ring-lime-400/30' },
  neutral: { label: 'Neutral', chip: 'bg-slate-400/15 text-slate-200 ring-1 ring-slate-400/30' },
};

const SPEAKER_SLOTS = 8;

/** Identity color of a speaker label: fixed categorical order, never by rank. */
export function speakerColor(label: string): string {
  if (label === 'Kognia') return 'var(--kv-violet)';
  const match = /Hablante (\d+)/.exec(label);
  if (!match) return 'var(--kv-ink-subtle)';
  const slot = Number(match[1]);
  return slot <= SPEAKER_SLOTS ? `var(--kv-series-${slot})` : 'var(--kv-ink-subtle)';
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(value);
}
