import { Routes } from '@angular/router';
import { HomeComponent } from "./pages/home/home.component";
import { GeneSetComponent } from "./pages/geneset/geneset.component";

export const appRoutes: Routes = [
    { path: '', component: HomeComponent },
    { path: 'home', component: HomeComponent },
    { path: 'search', component: HomeComponent, data: { searchIntent: true } },
    { path: 'geneset/:id', component: GeneSetComponent },
    { path: '**', redirectTo: '' }  // Handles undefined routes
];
