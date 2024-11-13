import { Routes } from '@angular/router';
import { HomeComponent } from "./pages/home/home.component";

export const appRoutes: Routes = [
    { path: '', component: HomeComponent },
    { path: 'home', component: HomeComponent },
    { path: 'search', component: HomeComponent, data: { searchIntent: true } },
    { path: '**', redirectTo: '' }  // Handles undefined routes
];
