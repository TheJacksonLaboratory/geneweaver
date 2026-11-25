import { Routes } from '@angular/router';
import { HomeComponent } from "./pages/home/home.component";

export const appRoutes: Routes = [
    { path: '', component: HomeComponent },
    { path: 'home', component: HomeComponent },
    { path: 'search', component: HomeComponent, data: { searchIntent: true } },
    // Lazy-loaded too: the gene set page and its similar gene sets charts (D3) are not
    // needed to show the search, and with Angular 21 and PrimeNG 21 eager they took the
    // initial bundle past the stage/prod budget (2 MB).
    {
        path: 'geneset/:id',
        loadComponent: () =>
            import('./pages/geneset/geneset.component').then(m => m.GeneSetComponent)
    },
    // Lazy-loaded: the analyze page pulls in PrimeNG table/chips/card modules that
    // nothing else needs, and the initial bundle is already close to its budget.
    {
        path: 'analyze',
        loadComponent: () =>
            import('./pages/analyze/analyze.component').then(m => m.AnalyzeComponent)
    },
    // The signed-in user's tool runs (G3-840); lazy, as only signed-in users get there.
    {
        path: 'analyses',
        loadComponent: () =>
            import('./pages/analyses/analyses.component').then(m => m.AnalysesComponent)
    },
    { path: '**', redirectTo: '' }  // Handles undefined routes
];
