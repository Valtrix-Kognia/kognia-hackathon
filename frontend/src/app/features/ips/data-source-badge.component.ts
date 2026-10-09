import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { Database, LucideAngularModule } from 'lucide-angular';
import { QueryMetadata } from '../../core/models/ips.model';

@Component({
  selector: 'app-data-source-badge',
  imports: [LucideAngularModule, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
      <span class="chip bg-brand-50 text-brand-700">
        <lucide-icon [img]="icon" [size]="12" />
        datos.gov.co · {{ metadata().dataset_id }}
      </span>
      <span>Consultado {{ metadata().queried_at | date: 'HH:mm:ss' }}</span>
      <a
        class="underline decoration-dotted underline-offset-2 hover:text-brand-600"
        href="https://www.datos.gov.co/d/{{ metadata().dataset_id }}"
        target="_blank"
        rel="noopener noreferrer"
        >Ver fuente oficial</a
      >
    </div>
  `,
})
export class DataSourceBadgeComponent {
  readonly metadata = input.required<QueryMetadata>();
  protected readonly icon = Database;
}
