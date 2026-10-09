import { Injectable, signal } from '@angular/core';

export type ToastKind = 'info' | 'success' | 'warning' | 'error';

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  private nextId = 1;
  private readonly items = signal<Toast[]>([]);
  readonly toasts = this.items.asReadonly();

  show(kind: ToastKind, message: string, durationMs = 5000): void {
    const id = this.nextId++;
    this.items.update((list) => [...list.filter((t) => t.message !== message), { id, kind, message }].slice(-4));
    if (durationMs > 0) {
      setTimeout(() => this.dismiss(id), durationMs);
    }
  }

  dismiss(id: number): void {
    this.items.update((list) => list.filter((t) => t.id !== id));
  }
}
