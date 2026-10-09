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
  positivo: { label: 'Positivo', dot: 'bg-emerald-500', bar: 'bg-emerald-500', text: 'text-emerald-700' },
  neutral: { label: 'Neutral', dot: 'bg-slate-400', bar: 'bg-slate-400', text: 'text-slate-600' },
  negativo: { label: 'Negativo', dot: 'bg-rose-500', bar: 'bg-rose-500', text: 'text-rose-700' },
};

export const EMOTION_META: Record<Emotion, { label: string; chip: string }> = {
  alegria: { label: 'Alegría', chip: 'bg-amber-100 text-amber-800' },
  tristeza: { label: 'Tristeza', chip: 'bg-sky-100 text-sky-800' },
  enojo: { label: 'Enojo', chip: 'bg-rose-100 text-rose-800' },
  miedo: { label: 'Miedo', chip: 'bg-violet-100 text-violet-800' },
  sorpresa: { label: 'Sorpresa', chip: 'bg-fuchsia-100 text-fuchsia-800' },
  asco: { label: 'Asco', chip: 'bg-lime-100 text-lime-800' },
  neutral: { label: 'Neutral', chip: 'bg-slate-100 text-slate-700' },
};

const SPEAKER_PALETTE = [
  'bg-sky-100 text-sky-800 ring-sky-200',
  'bg-violet-100 text-violet-800 ring-violet-200',
  'bg-amber-100 text-amber-800 ring-amber-200',
  'bg-teal-100 text-teal-800 ring-teal-200',
  'bg-pink-100 text-pink-800 ring-pink-200',
];

export function speakerColor(label: string): string {
  if (label === 'Kognia') return 'bg-brand-700 text-white ring-brand-800';
  const match = /Hablante (\d+)/.exec(label);
  if (!match) return 'bg-slate-100 text-slate-600 ring-slate-200';
  return SPEAKER_PALETTE[(Number(match[1]) - 1) % SPEAKER_PALETTE.length];
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(value);
}
