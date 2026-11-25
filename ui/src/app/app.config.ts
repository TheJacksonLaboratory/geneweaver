import { ApplicationConfig, provideZonelessChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { appRoutes } from './app.routes';
import { provideAnimations } from '@angular/platform-browser/animations';
import { provideHttpClient } from '@angular/common/http';
import { providePrimeNG } from 'primeng/config';
import { GeneWeaverPreset } from './theme';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZonelessChangeDetection(),
    provideRouter(appRoutes),
    provideAnimations(),
    provideHttpClient(),
    providePrimeNG({
      theme: {
        preset: GeneWeaverPreset,
        options: {
          // Light only, as PrimeNG 17's aura-light theme was: the class is never set, so
          // the OS's dark mode does not switch the app to Aura's dark palette.
          darkModeSelector: '.gw-dark-mode',
          // No cascade layer: PrimeNG's styles then sit after the app's and win on
          // specificity, as PrimeNG 17's theme did -- a global `a { color }` does not recolour
          // menu links -- while PrimeFlex's utilities, all !important, still win over both.
        },
      },
    }),
  ],
};
