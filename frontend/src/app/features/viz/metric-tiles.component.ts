import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MetricSpec } from '../../core/models/visualization.model';
import { formatNumber } from '../../shared/utils/labels';

@Component({
  selector: 'app-metric-tiles',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <dl class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      @for (item of spec().items; track item.label) {
        <div
          class="rounded-xl p-4 ring-1"
          [class]="item.emphasis ? 'bg-kv-primary/10 ring-kv-primary/40' : 'bg-kv-bg/50 ring-kv-border'"
        >
          <dt class="text-xs text-kv-muted">{{ item.label }}</dt>
          <dd class="tabular mt-1 text-3xl font-semibold tracking-tight text-kv-ink">{{ fmt(item.value) }}</dd>
          <dd class="mt-0.5 text-[11px] text-kv-subtle">{{ item.unit }}</dd>
        </div>
      }
    </dl>
  `,
})
export class MetricTilesComponent {
  readonly spec = input.required<MetricSpec>();
  protected readonly fmt = formatNumber;
}
