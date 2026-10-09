import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ExtendedFeature, ExtendedFeatureCollection, geoMercator, geoPath } from 'd3-geo';
import { formatNumber } from '../../shared/utils/labels';
import { ChoroplethClass, colorFor } from './choropleth-scale';
import { DepartmentValue, ISO_NAMES } from './department-catalog';
import { DepartmentCollection, GeoDataService } from './geo-data.service';

const WIDTH = 560;
const HEIGHT = 640;
const INSET = { x: 12, y: 12, w: 96, h: 120 };
const ISLANDS_ISO = 'CO-SAP';

interface ShapePath {
  iso: string;
  name: string;
  d: string;
  centroid: [number, number];
  bounds: [[number, number], [number, number]];
  inset: boolean;
}

@Component({
  selector: 'app-colombia-map',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (shapes(); as list) {
      <div class="relative">
        <svg
          [attr.viewBox]="viewBox()"
          class="h-auto w-full transition-[viewBox] duration-500"
          role="group"
          aria-label="Mapa coroplético de Colombia por departamento"
          (keydown.escape)="selected.emit(null)"
        >
          <defs>
            <pattern id="kv-no-data" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
              <rect width="6" height="6" fill="var(--kv-no-data)" />
              <line x1="0" y1="0" x2="0" y2="6" stroke="#46557a" stroke-width="2" />
            </pattern>
          </defs>
          <rect
            [attr.x]="inset.x"
            [attr.y]="inset.y"
            [attr.width]="inset.w"
            [attr.height]="inset.h"
            rx="8"
            fill="none"
            stroke="var(--kv-border)"
            stroke-dasharray="3 3"
          />
          <text [attr.x]="inset.x + 6" [attr.y]="inset.y + inset.h + 14" class="fill-kv-subtle text-[10px]">San Andrés y Prov.</text>
          @for (shape of list; track shape.iso) {
            <path
              [attr.d]="shape.d"
              [attr.fill]="fillFor(shape.iso)"
              [attr.stroke]="strokeFor(shape.iso)"
              [attr.stroke-width]="strokeWidthFor(shape.iso)"
              class="cursor-pointer outline-none transition-[fill,opacity] duration-300 hover:opacity-90 focus-visible:opacity-90"
              [class.opacity-40]="selectedIso() && selectedIso() !== shape.iso"
              tabindex="0"
              role="button"
              [attr.aria-label]="ariaLabel(shape)"
              [attr.aria-pressed]="selectedIso() === shape.iso"
              (mouseenter)="hovered.set(shape.iso)"
              (mouseleave)="hovered.set(null)"
              (focus)="hovered.set(shape.iso)"
              (blur)="hovered.set(null)"
              (click)="toggle(shape.iso)"
              (keydown.enter)="toggle(shape.iso)"
              (keydown.space)="$event.preventDefault(); toggle(shape.iso)"
            />
          }
        </svg>

        @if (tooltip(); as tip) {
          <div
            class="pointer-events-none absolute z-10 min-w-40 rounded-lg border border-kv-border bg-kv-elevated/95 px-3 py-2 text-xs shadow-xl backdrop-blur"
            [style.left.%]="tip.left"
            [style.top.%]="tip.top"
            style="transform: translate(-50%, -115%)"
            role="status"
          >
            <p class="font-semibold text-kv-ink">{{ tip.name }}</p>
            @if (tip.value !== null) {
              <p class="tabular mt-0.5 text-kv-ink">{{ tip.value }} <span class="text-kv-muted">{{ unitLabel() }}</span></p>
              @if (tip.sources.length > 1) {
                <p class="mt-1 text-kv-muted">Incluye: {{ tip.sources.join(' + ') }}</p>
              }
            } @else {
              <p class="mt-0.5 text-kv-muted">Sin datos en la fuente para este filtro</p>
            }
          </div>
        }
      </div>
    } @else {
      <div class="skeleton aspect-[7/8] w-full" aria-busy="true" aria-label="Cargando mapa"></div>
    }
  `,
})
export class ColombiaMapComponent {
  readonly values = input.required<Map<string, DepartmentValue>>();
  readonly classes = input.required<ChoroplethClass[]>();
  readonly highlighted = input<string[]>([]);
  readonly selectedIso = input<string | null>(null);
  readonly unitLabel = input('sedes');
  readonly selected = output<string | null>();

  protected readonly inset = INSET;
  protected readonly hovered = signal<string | null>(null);
  private readonly geo = toSignal(inject(GeoDataService).departments$);

  protected readonly shapes = computed(() => {
    const collection = this.geo();
    return collection ? buildShapes(collection) : null;
  });

  protected readonly viewBox = computed(() => {
    const iso = this.selectedIso();
    const shape = iso ? this.shapes()?.find((s) => s.iso === iso) : null;
    if (!shape || shape.inset) return `0 0 ${WIDTH} ${HEIGHT}`;
    const [[x0, y0], [x1, y1]] = shape.bounds;
    const pad = 40;
    const size = Math.max(x1 - x0, (y1 - y0) * (WIDTH / HEIGHT), 120) + pad * 2;
    const height = size * (HEIGHT / WIDTH);
    const cx = (x0 + x1) / 2;
    const cy = (y0 + y1) / 2;
    return `${cx - size / 2} ${cy - height / 2} ${size} ${height}`;
  });

  protected readonly tooltip = computed(() => {
    const iso = this.hovered();
    const shape = iso ? this.shapes()?.find((s) => s.iso === iso) : null;
    if (!shape) return null;
    const value = this.values().get(shape.iso);
    return {
      name: shape.name,
      value: value ? formatNumber(value.value) : null,
      sources: value?.sources ?? [],
      left: (shape.centroid[0] / WIDTH) * 100,
      top: (shape.centroid[1] / HEIGHT) * 100,
    };
  });

  protected fillFor(iso: string): string {
    return colorFor(this.values().get(iso)?.value, this.classes()) ?? 'url(#kv-no-data)';
  }

  protected strokeFor(iso: string): string {
    if (this.selectedIso() === iso) return 'var(--kv-ink)';
    if (this.highlighted().includes(iso)) return 'var(--kv-accent)';
    return 'var(--kv-bg)';
  }

  protected strokeWidthFor(iso: string): number {
    return this.selectedIso() === iso || this.highlighted().includes(iso) ? 2 : 0.8;
  }

  protected ariaLabel(shape: ShapePath): string {
    const value = this.values().get(shape.iso);
    const amount = value ? `${formatNumber(value.value)} ${this.unitLabel()}` : 'sin datos';
    const flag = this.highlighted().includes(shape.iso) ? ', mencionado por Kognia' : '';
    return `${shape.name}: ${amount}${flag}`;
  }

  protected toggle(iso: string): void {
    this.selected.emit(this.selectedIso() === iso ? null : iso);
  }
}

function buildShapes(collection: DepartmentCollection): ShapePath[] {
  const mainland = { ...collection, features: collection.features.filter((f) => f.properties.iso !== ISLANDS_ISO) };
  const islands = { ...collection, features: collection.features.filter((f) => f.properties.iso === ISLANDS_ISO) };
  const asCollection = (c: unknown) => c as ExtendedFeatureCollection;
  const asFeature = (f: unknown) => f as ExtendedFeature;
  const mainProjection = geoMercator().fitExtent([[INSET.x + INSET.w + 8, 8], [WIDTH - 8, HEIGHT - 8]], asCollection(mainland));
  const insetProjection = geoMercator().fitExtent(
    [[INSET.x + 8, INSET.y + 8], [INSET.x + INSET.w - 8, INSET.y + INSET.h - 8]],
    asCollection(islands),
  );
  return collection.features.map((feature) => {
    const inset = feature.properties.iso === ISLANDS_ISO;
    const path = geoPath(inset ? insetProjection : mainProjection);
    const [cx, cy] = path.centroid(asFeature(feature));
    const bounds = path.bounds(asFeature(feature)) as [[number, number], [number, number]];
    return {
      iso: feature.properties.iso,
      name: ISO_NAMES[feature.properties.iso] ?? feature.properties.name,
      d: path(asFeature(feature)) ?? '',
      centroid: [cx, cy],
      bounds,
      inset,
    };
  });
}
