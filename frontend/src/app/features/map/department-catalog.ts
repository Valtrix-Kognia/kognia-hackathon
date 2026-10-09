import { CategoryDatum } from '../../core/models/visualization.model';

/**
 * Controlled catalog: values of the `departamento` column in s2ru-bqt6 -> ISO 3166-2 code of
 * the geoBoundaries COL ADM1 polygons. Districts reported as separate rows in the dataset are
 * mapped to the department that contains them.
 */
const CATALOG: Record<string, { iso: string; district?: boolean }> = {
  AMAZONAS: { iso: 'CO-AMA' },
  ANTIOQUIA: { iso: 'CO-ANT' },
  ARAUCA: { iso: 'CO-ARA' },
  ATLANTICO: { iso: 'CO-ATL' },
  BARRANQUILLA: { iso: 'CO-ATL', district: true },
  'BOGOTA D C': { iso: 'CO-DC' },
  BOGOTA: { iso: 'CO-DC' },
  BOLIVAR: { iso: 'CO-BOL' },
  CARTAGENA: { iso: 'CO-BOL', district: true },
  BOYACA: { iso: 'CO-BOY' },
  CALDAS: { iso: 'CO-CAL' },
  CAQUETA: { iso: 'CO-CAQ' },
  CASANARE: { iso: 'CO-CAS' },
  CAUCA: { iso: 'CO-CAU' },
  CESAR: { iso: 'CO-CES' },
  CHOCO: { iso: 'CO-CHO' },
  CORDOBA: { iso: 'CO-COR' },
  CUNDINAMARCA: { iso: 'CO-CUN' },
  GUAINIA: { iso: 'CO-GUA' },
  GUAVIARE: { iso: 'CO-GUV' },
  HUILA: { iso: 'CO-HUI' },
  'LA GUAJIRA': { iso: 'CO-LAG' },
  MAGDALENA: { iso: 'CO-MAG' },
  'SANTA MARTA': { iso: 'CO-MAG', district: true },
  META: { iso: 'CO-MET' },
  NARINO: { iso: 'CO-NAR' },
  'NORTE DE SANTANDER': { iso: 'CO-NSA' },
  PUTUMAYO: { iso: 'CO-PUT' },
  QUINDIO: { iso: 'CO-QUI' },
  RISARALDA: { iso: 'CO-RIS' },
  'SAN ANDRES Y PROVIDENCIA': { iso: 'CO-SAP' },
  SANTANDER: { iso: 'CO-SAN' },
  SUCRE: { iso: 'CO-SUC' },
  TOLIMA: { iso: 'CO-TOL' },
  'VALLE DEL CAUCA': { iso: 'CO-VAC' },
  CALI: { iso: 'CO-VAC', district: true },
  BUENAVENTURA: { iso: 'CO-VAC', district: true },
  VAUPES: { iso: 'CO-VAU' },
  VICHADA: { iso: 'CO-VID' },
};

/** Display names for ISO codes (Spanish, official department names). */
export const ISO_NAMES: Record<string, string> = {
  'CO-AMA': 'Amazonas',
  'CO-ANT': 'Antioquia',
  'CO-ARA': 'Arauca',
  'CO-ATL': 'Atlántico',
  'CO-DC': 'Bogotá D.C.',
  'CO-BOL': 'Bolívar',
  'CO-BOY': 'Boyacá',
  'CO-CAL': 'Caldas',
  'CO-CAQ': 'Caquetá',
  'CO-CAS': 'Casanare',
  'CO-CAU': 'Cauca',
  'CO-CES': 'Cesar',
  'CO-CHO': 'Chocó',
  'CO-COR': 'Córdoba',
  'CO-CUN': 'Cundinamarca',
  'CO-GUA': 'Guainía',
  'CO-GUV': 'Guaviare',
  'CO-HUI': 'Huila',
  'CO-LAG': 'La Guajira',
  'CO-MAG': 'Magdalena',
  'CO-MET': 'Meta',
  'CO-NAR': 'Nariño',
  'CO-NSA': 'Norte de Santander',
  'CO-PUT': 'Putumayo',
  'CO-QUI': 'Quindío',
  'CO-RIS': 'Risaralda',
  'CO-SAP': 'San Andrés y Providencia',
  'CO-SAN': 'Santander',
  'CO-SUC': 'Sucre',
  'CO-TOL': 'Tolima',
  'CO-VAC': 'Valle del Cauca',
  'CO-VAU': 'Vaupés',
  'CO-VID': 'Vichada',
};

/** The dataset value to send back to the API when a department polygon is selected. */
export const ISO_TO_DATASET_VALUE: Record<string, string> = {
  'CO-DC': 'Bogotá D.C',
  'CO-SAP': 'San Andrés y Providencia',
  'CO-VAC': 'Valle del cauca',
};

export function normalizePlace(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toUpperCase()
    .replace(/[^A-Z0-9 ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function isoForDatasetValue(value: string): { iso: string; district: boolean } | null {
  const entry = CATALOG[normalizePlace(value)];
  return entry ? { iso: entry.iso, district: !!entry.district } : null;
}

export interface DepartmentValue {
  iso: string;
  value: number;
  /** Dataset rows that were added up (department + districts inside it). */
  sources: string[];
}

export interface AggregatedByDepartment {
  values: Map<string, DepartmentValue>;
  /** Dataset values that did not match any polygon (reported, never dropped silently). */
  unmatched: CategoryDatum[];
  districtsMerged: string[];
}

/** Sum dataset rows into department polygons. Only valid for additive metrics. */
export function aggregateByDepartment(data: CategoryDatum[]): AggregatedByDepartment {
  const values = new Map<string, DepartmentValue>();
  const unmatched: CategoryDatum[] = [];
  const districtsMerged: string[] = [];
  for (const datum of data) {
    const match = isoForDatasetValue(datum.label);
    if (!match) {
      unmatched.push(datum);
      continue;
    }
    if (match.district) districtsMerged.push(datum.label);
    const current = values.get(match.iso);
    values.set(match.iso, {
      iso: match.iso,
      value: (current?.value ?? 0) + datum.value,
      sources: [...(current?.sources ?? []), datum.label],
    });
  }
  return { values, unmatched, districtsMerged };
}

export function datasetValueForIso(iso: string): string {
  return ISO_TO_DATASET_VALUE[iso] ?? ISO_NAMES[iso] ?? iso;
}
