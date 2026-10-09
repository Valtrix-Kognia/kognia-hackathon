import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { CircleAlert, CircleCheck, Info, LucideAngularModule, TriangleAlert, X } from 'lucide-angular';
import { ToastKind, ToastService } from '../../core/services/toast.service';

@Component({
  selector: 'app-toast-container',
  imports: [LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 sm:items-end sm:pr-6">
      @for (toast of toasts.toasts(); track toast.id) {
        <div
          class="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border bg-kv-surface px-4 py-3 text-sm shadow-lg {{ styles[toast.kind].border }}"
          [attr.role]="toast.kind === 'error' ? 'alert' : 'status'"
        >
          <lucide-icon [img]="styles[toast.kind].icon" [size]="18" class="mt-0.5 shrink-0 {{ styles[toast.kind].color }}" />
          <p class="flex-1 text-kv-ink">{{ toast.message }}</p>
          <button type="button" class="text-kv-subtle hover:text-kv-muted" (click)="toasts.dismiss(toast.id)" aria-label="Cerrar aviso">
            <lucide-icon [img]="closeIcon" [size]="16" />
          </button>
        </div>
      }
    </div>
  `,
})
export class ToastContainerComponent {
  protected readonly toasts = inject(ToastService);
  protected readonly closeIcon = X;
  protected readonly styles: Record<ToastKind, { icon: typeof Info; color: string; border: string }> = {
    info: { icon: Info, color: 'text-kv-primary', border: 'border-kv-primary/40' },
    success: { icon: CircleCheck, color: 'text-emerald-500', border: 'border-kv-border' },
    warning: { icon: TriangleAlert, color: 'text-amber-500', border: 'border-kv-border' },
    error: { icon: CircleAlert, color: 'text-rose-500', border: 'border-kv-border' },
  };
}
