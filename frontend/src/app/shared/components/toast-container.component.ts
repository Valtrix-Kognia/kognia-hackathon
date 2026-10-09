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
          class="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border bg-white px-4 py-3 text-sm shadow-lg {{ styles[toast.kind].border }}"
          [attr.role]="toast.kind === 'error' ? 'alert' : 'status'"
        >
          <lucide-icon [img]="styles[toast.kind].icon" [size]="18" class="mt-0.5 shrink-0 {{ styles[toast.kind].color }}" />
          <p class="flex-1 text-slate-700">{{ toast.message }}</p>
          <button type="button" class="text-slate-400 hover:text-slate-600" (click)="toasts.dismiss(toast.id)" aria-label="Cerrar aviso">
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
    info: { icon: Info, color: 'text-brand-500', border: 'border-brand-100' },
    success: { icon: CircleCheck, color: 'text-emerald-500', border: 'border-emerald-100' },
    warning: { icon: TriangleAlert, color: 'text-amber-500', border: 'border-amber-100' },
    error: { icon: CircleAlert, color: 'text-rose-500', border: 'border-rose-100' },
  };
}
