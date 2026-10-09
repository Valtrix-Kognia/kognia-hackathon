import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import countQuindio from '../../../testing/fixtures/count-quindio.json';
import groupDepartamento from '../../../testing/fixtures/group-departamento-sedes.json';
import groupNaturaleza from '../../../testing/fixtures/group-naturaleza-antioquia.json';
import { EventType, RealtimeEvent } from '../../core/models/realtime-event.model';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { DashboardStateService } from '../../core/services/dashboard-state.service';
import { MapStateService } from '../map/map-state.service';
import { EvidencePanelComponent } from '../evidence/evidence-panel.component';
import { VisualizationPanelComponent } from './visualization-panel.component';

// Fixtures are responses recorded from the Kognia API (datos.gov.co s2ru-bqt6) on 2026-10-09.

let seq = 0;
function event<T>(type: EventType, payload: T): RealtimeEvent<T> {
  return { type, seq: ++seq, session_id: 'room-ui', emitted_at: new Date().toISOString(), payload };
}

function completeQuery(store: ConversationStore, id: string, tool: string, result: unknown): void {
  store.apply(event('ips.query.started', { query_id: id, tool, arguments: {} }));
  store.apply(event('ips.query.completed', { query_id: id, tool, arguments: {}, result }));
}

describe('generative dashboard with recorded official data', () => {
  let store: ConversationStore;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    store = TestBed.inject(ConversationStore);
    store.reset('room-ui');
  });

  it('renders metric tiles with the exact API counts', async () => {
    completeQuery(store, 'q-count', 'count_ips', countQuindio);
    const fixture = TestBed.createComponent(VisualizationPanelComponent);
    await fixture.whenStable();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Quindío');
    expect(text).toContain('139');
    expect(text).toContain('148');
    expect(text).toContain('469');
    expect(text).toContain('s2ru-bqt6');
  });

  it('renders a department ranking as bars and table, and updates the map context', async () => {
    const map = TestBed.inject(MapStateService);
    TestBed.inject(DashboardStateService);
    completeQuery(store, 'q-rank', 'group_ips', groupDepartamento);
    const fixture = TestBed.createComponent(VisualizationPanelComponent);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelectorAll('app-bar-chart li').length).toBe(5);
    expect(el.querySelector('app-data-table')?.textContent).toContain('1.270');
    expect(el.textContent).toContain('Ver 5 departamentos en el mapa');
    expect(map.context().origin).toBe('respuesta_kognia');
    expect(map.context().highlighted).toContain('CO-DC');
    expect(map.context().highlighted).toContain('CO-VAC');
  });

  it('renders few categories as a donut with percentages from the API values', async () => {
    completeQuery(store, 'q-nat', 'group_ips', groupNaturaleza);
    const fixture = TestBed.createComponent(VisualizationPanelComponent);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('app-donut-chart')).not.toBeNull();
    expect(el.textContent).toContain('979');
    expect(el.textContent).toContain('87.8 %');
  });

  it('shows provenance, filters and limitations in the evidence panel', async () => {
    completeQuery(store, 'q-count', 'count_ips', countQuindio);
    const fixture = TestBed.createComponent(EvidencePanelComponent);
    await fixture.whenStable();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Datos verificados en la fuente oficial');
    expect(text).toContain('Departamento: Quindío');
    expect(text).toContain('Conteo de IPS');
    expect(text).toContain('Limitaciones');
  });

  it('shows an explicit error and no figures when the query fails', async () => {
    store.apply(event('ips.query.started', { query_id: 'q-bad', tool: 'count_ips', arguments: {} }));
    store.apply(event('ips.query.failed', { query_id: 'q-bad', tool: 'count_ips', arguments: {}, message: 'La API oficial no respondió.' }));
    const fixture = TestBed.createComponent(VisualizationPanelComponent);
    await fixture.whenStable();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('La API oficial no respondió.');
    expect(fixture.nativeElement.querySelector('app-metric-tiles')).toBeNull();
  });
});
