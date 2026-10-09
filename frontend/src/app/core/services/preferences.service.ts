import { Injectable, effect, signal } from '@angular/core';

export const FONT_SCALES = [0.9, 1, 1.15, 1.3] as const;
const STORAGE_KEY = 'kognia.preferences';

interface Preferences {
  fontScale: number;
  captions: boolean;
}

/** Per-browser display preferences; storage failures fall back to defaults. */
@Injectable({ providedIn: 'root' })
export class PreferencesService {
  readonly fontScale = signal<number>(1);
  readonly captions = signal(true);

  constructor() {
    const saved = readSaved();
    if (saved) {
      if ((FONT_SCALES as readonly number[]).includes(saved.fontScale)) this.fontScale.set(saved.fontScale);
      this.captions.set(saved.captions !== false);
    }
    effect(() => {
      document.documentElement.style.setProperty('--kv-font-scale', String(this.fontScale()));
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ fontScale: this.fontScale(), captions: this.captions() }));
      } catch {
        // storage unavailable (private mode, blocked): preferences stay in memory
      }
    });
  }

  stepFont(direction: 1 | -1): void {
    const index = FONT_SCALES.indexOf(this.fontScale() as (typeof FONT_SCALES)[number]);
    const next = Math.min(FONT_SCALES.length - 1, Math.max(0, (index < 0 ? 1 : index) + direction));
    this.fontScale.set(FONT_SCALES[next]);
  }
}

function readSaved(): Preferences | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Preferences) : null;
  } catch {
    return null;
  }
}
