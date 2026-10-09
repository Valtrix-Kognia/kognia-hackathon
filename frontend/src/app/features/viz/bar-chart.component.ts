import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { CategoryChartSpec } from '../../core/models/visualization.model';
import { formatNumber } from '../../shared/utils/labels';

const ROW_HEIGHT = 28;
const MAX_ROWS = 15;

/** Horizontal bars: one series, single color, thin marks, value labels outside the bar. */
@Component({
  selector: 'app-bar-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <figure class="relative">
      <ol class="space-y-1" role="list" [attr.aria-label]="spec().title">
        @for (row of rows(); track row.label; let i = $index) {
          <li
            class="group grid cursor-default grid-cols-[minmax(6rem,10rem)_1fr_auto] items-center gap-3 rounded-md px-1 text-sm"
            [style.height.px]="rowHeight"
            tabindex="0"
            [attr.aria-label]="row.label + ': ' + fmt(row.value) + ' ' + spec().unit"
            (mouseenter)="active.set(i)"
            (mouseleave)="active.set(null)"
            (focus)="active.set(i)"
            (blur)="active.set(null)"
            [class.bg-kv-elevated]="active() === i"
          >
            <span class="truncate text-kv-muted group-hover:text-kv-ink" [title]="row.label">{{ row.label }}</span>
            <span class="relative h-3" aria-hidden="true">
              <span
                class="absolute inset-y-0 left-0 rounded-r-[4px] bg-[var(--kv-series-1)] transition-[width] duration-500"
                [style.width.%]="row.pct"
              ></span>
            </span>
            <span class="tabular w-16 text-right text-kv-ink">{{ fmt(row.value) }}</span>
          </li>
        } @empty {
          <li class="py-6 text-center text-sm text-kv-muted">La consulta no devolvió datos.</li>
        }
      </ol>
      @if (hiddenCount() > 0) {
        <figcaption class="mt-2 text-xs text-kv-subtle">Se muestran {{ rows().length }} de {{ spec().data.length }}; la tabla tiene todos.</figcaption>
      }
    </figure>
  `,
})
export class BarChartComponent {
  readonly spec = input.required<CategoryChartSpec>();
  protected readonly rowHeight = ROW_HEIGHT;
  protected readonly active = signal<number | null>(null);
  protected readonly fmt = formatNumber;

  protected readonly rows = computed(() => {
    const data = this.spec().data.slice(0, MAX_ROWS);
    const max = Math.max(1, ...data.map((d) => d.value));
    return data.map((d) => ({ ...d, pct: (d.value / max) * 100 }));
  });

  protected readonly hiddenCount = computed(() => this.spec().data.length - this.rows().length);
}
