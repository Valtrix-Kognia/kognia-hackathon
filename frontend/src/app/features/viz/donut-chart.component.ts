import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { CategoryChartSpec } from '../../core/models/visualization.model';
import { formatNumber } from '../../shared/utils/labels';

const SERIES = [
  'var(--kv-series-1)',
  'var(--kv-series-2)',
  'var(--kv-series-3)',
  'var(--kv-series-4)',
  'var(--kv-series-5)',
  'var(--kv-series-6)',
];
const RADIUS = 70;
const STROKE = 22;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const GAP = 2;

/** Part-to-whole for <= 6 categories; colors follow the fixed categorical order. */
@Component({
  selector: 'app-donut-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <figure class="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
      <svg viewBox="0 0 200 200" class="h-44 w-44 shrink-0 -rotate-90" role="img" [attr.aria-label]="ariaSummary()">
        <circle cx="100" cy="100" [attr.r]="radius" fill="none" stroke="var(--kv-bg)" [attr.stroke-width]="stroke" />
        @for (arc of arcs(); track arc.label; let i = $index) {
          <circle
            cx="100"
            cy="100"
            [attr.r]="radius"
            fill="none"
            [attr.stroke]="arc.color"
            [attr.stroke-width]="active() === i ? stroke + 4 : stroke"
            [attr.stroke-dasharray]="arc.dash"
            [attr.stroke-dashoffset]="arc.offset"
            class="transition-[stroke-width] duration-200"
            (mouseenter)="active.set(i)"
            (mouseleave)="active.set(null)"
          />
        }
      </svg>
      <ul class="w-full space-y-1.5 text-sm">
        @for (arc of arcs(); track arc.label; let i = $index) {
          <li
            class="flex items-center gap-2 rounded-md px-2 py-1"
            [class.bg-kv-elevated]="active() === i"
            tabindex="0"
            (focus)="active.set(i)"
            (blur)="active.set(null)"
            (mouseenter)="active.set(i)"
            (mouseleave)="active.set(null)"
          >
            <span class="h-3 w-3 shrink-0 rounded-sm" [style.background]="arc.color" aria-hidden="true"></span>
            <span class="flex-1 text-kv-ink">{{ arc.label }}</span>
            <span class="tabular text-kv-ink">{{ fmt(arc.value) }}</span>
            <span class="tabular w-12 text-right text-kv-muted">{{ arc.pct }} %</span>
          </li>
        }
      </ul>
    </figure>
  `,
})
export class DonutChartComponent {
  readonly spec = input.required<CategoryChartSpec>();
  protected readonly radius = RADIUS;
  protected readonly stroke = STROKE;
  protected readonly active = signal<number | null>(null);
  protected readonly fmt = formatNumber;

  protected readonly arcs = computed(() => {
    const data = this.spec().data;
    const total = data.reduce((sum, d) => sum + d.value, 0) || 1;
    let cumulative = 0;
    return data.map((d, i) => {
      const length = Math.max(0, (d.value / total) * CIRCUMFERENCE - GAP);
      const arc = {
        label: d.label,
        value: d.value,
        color: SERIES[i % SERIES.length],
        pct: Math.round((d.value / total) * 1000) / 10,
        dash: `${length} ${CIRCUMFERENCE}`,
        offset: -cumulative,
      };
      cumulative += (d.value / total) * CIRCUMFERENCE;
      return arc;
    });
  });

  protected readonly ariaSummary = computed(
    () => `${this.spec().title}: ` + this.arcs().map((a) => `${a.label} ${a.pct} %`).join(', '),
  );
}
