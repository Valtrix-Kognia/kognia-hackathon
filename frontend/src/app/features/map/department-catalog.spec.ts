import { colorFor, quantileClasses } from './choropleth-scale';
import { ISO_NAMES, aggregateByDepartment, datasetValueForIso, isoForDatasetValue, normalizePlace } from './department-catalog';

describe('department catalog', () => {
  it('normalizes accents, case and punctuation', () => {
    expect(normalizePlace('Bogotá D.C')).toBe('BOGOTA D C');
    expect(normalizePlace('  quindío ')).toBe('QUINDIO');
  });

  it('maps every dataset department value (incl. districts) to a known polygon', () => {
    const values = [
      'Amazonas', 'Antioquia', 'Arauca', 'Atlántico', 'Barranquilla', 'Bogotá D.C', 'Bolívar', 'Boyacá',
      'Buenaventura', 'Caldas', 'Cali', 'Caquetá', 'Cartagena', 'Casanare', 'Cauca', 'Cesar', 'Chocó',
      'Córdoba', 'Cundinamarca', 'Guainía', 'Guaviare', 'Huila', 'La Guajira', 'Magdalena', 'Meta', 'Nariño',
      'Norte de Santander', 'Putumayo', 'Quindío', 'Risaralda', 'San Andrés y Providencia', 'Santa Marta',
      'Santander', 'Sucre', 'Tolima', 'Valle del cauca', 'Vaupés', 'Vichada',
    ];
    for (const value of values) {
      const match = isoForDatasetValue(value);
      expect(match, value).not.toBeNull();
      expect(ISO_NAMES[match!.iso], value).toBeDefined();
    }
  });

  it('adds districts to their department and reports unmatched values', () => {
    const result = aggregateByDepartment([
      { label: 'Valle del cauca', value: 10 },
      { label: 'Cali', value: 5 },
      { label: 'Buenaventura', value: 1 },
      { label: 'Atlantis', value: 3 },
    ]);
    expect(result.values.get('CO-VAC')).toEqual({ iso: 'CO-VAC', value: 16, sources: ['Valle del cauca', 'Cali', 'Buenaventura'] });
    expect(result.districtsMerged).toEqual(['Cali', 'Buenaventura']);
    expect(result.unmatched).toEqual([{ label: 'Atlantis', value: 3 }]);
  });

  it('returns the dataset value to query for a polygon', () => {
    expect(datasetValueForIso('CO-DC')).toBe('Bogotá D.C');
    expect(datasetValueForIso('CO-QUI')).toBe('Quindío');
  });
});

describe('choropleth scale', () => {
  it('builds monotone quantile classes covering all values', () => {
    const classes = quantileClasses([1, 2, 3, 4, 5, 6, 100, 1000]);
    expect(classes[0].min).toBe(1);
    expect(classes.at(-1)!.max).toBe(1000);
    for (let i = 1; i < classes.length; i++) expect(classes[i].min).toBeGreaterThan(classes[i - 1].max);
  });

  it('distinguishes missing data from zero', () => {
    const classes = quantileClasses([0, 5, 10]);
    expect(colorFor(undefined, classes)).toBeNull();
    expect(colorFor(0, classes)).not.toBeNull();
  });
});
