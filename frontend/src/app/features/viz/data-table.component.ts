import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { TableSpec } from '../../core/models/visualization.model';
import { formatNumber } from '../../shared/utils/labels';

@Component({
  selector: 'app-data-table',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="max-h-80 overflow-auto rounded-xl ring-1 ring-kv-border">
      <table class="min-w-full text-left text-sm">
        <caption class="sr-only">{{ spec().title }}</caption>
        <thead class="sticky top-0 bg-kv-elevated text-[11px] uppercase tracking-wide text-kv-muted">
          <tr>
            @for (col of spec().columns; track col.key) {
              <th scope="col" class="px-3 py-2 font-medium" [class.text-right]="col.numeric">{{ col.label }}</th>
            }
          </tr>
        </thead>
        <tbody class="divide-y divide-kv-border">
          @for (row of spec().rows; track $index) {
            <tr class="hover:bg-kv-elevated/50">
              @for (col of spec().columns; track col.key) {
                <td class="px-3 py-2" [class.text-right]="col.numeric" [class.tabular]="col.numeric">{{ cell(row[col.key], col.numeric) }}</td>
              }
            </tr>
          } @empty {
            <tr><td [attr.colspan]="spec().columns.length" class="px-3 py-6 text-center text-kv-muted">Sin resultados para estos filtros.</td></tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class DataTableComponent {
  readonly spec = input.required<TableSpec>();

  protected cell(value: string | number | null | undefined, numeric?: boolean): string {
    if (value === null || value === undefined || value === '') return 'Sin dato';
    return numeric && typeof value === 'number' ? formatNumber(value) : String(value);
  }
}
