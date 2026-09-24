import { Routes } from '@angular/router';
import { HomeComponent } from "./pages/home/home.component";
import { GeneSetComponent } from "./pages/geneset/geneset.component";

export const appRoutes: Routes = [
    { path: '', component: HomeComponent },
    { path: 'home', component: HomeComponent },
    { path: 'search', component: HomeComponent, data: { searchIntent: true } },
    { path: 'geneset/:id', component: GeneSetComponent },
    // Lazy-loaded: the analyze page pulls in PrimeNG table/chips/card modules that
    // nothing else needs, and the initial bundle is already close to its budget.
    {
        path: 'analyze',
        loadComponent: () =>
            import('./pages/analyze/analyze.component').then(m => m.AnalyzeComponent)
    },
    { path: '**', redirectTo: '' }  // Handles undefined routes
];
