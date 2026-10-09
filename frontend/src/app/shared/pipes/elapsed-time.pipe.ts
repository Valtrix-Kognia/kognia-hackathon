import { Pipe, PipeTransform } from '@angular/core';

/** Formats milliseconds since session start as mm:ss. */
@Pipe({ name: 'elapsedTime' })
export class ElapsedTimePipe implements PipeTransform {
  transform(ms: number | null | undefined): string {
    if (ms == null || ms < 0) return '--:--';
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }
}
