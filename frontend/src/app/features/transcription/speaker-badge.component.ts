import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { speakerColor } from '../../shared/utils/labels';

@Component({
  selector: 'app-speaker-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="chip ring-1 ring-inset {{ color() }}" [title]="title()">
      {{ label() }}
    </span>
  `,
})
export class SpeakerBadgeComponent {
  readonly label = input.required<string>();
  protected readonly color = computed(() => speakerColor(this.label()));
  protected readonly title = computed(() =>
    this.label() === 'Kognia'
      ? 'Agente de voz'
      : this.label() === 'Hablante desconocido'
        ? 'La diarización no pudo identificar al hablante con confianza'
        : 'Hablante identificado por diarización acústica',
  );
}
