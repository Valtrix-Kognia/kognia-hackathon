import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./features/dashboard/dashboard-page.component').then((m) => m.DashboardPageComponent),
    title: 'Kognia Voice · IPS de Colombia',
  },
  { path: '**', redirectTo: '' },
];
