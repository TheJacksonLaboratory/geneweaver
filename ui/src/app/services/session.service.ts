import { Injectable } from '@angular/core';
import { ApiBaseService, ApiBaseServiceFactory } from 'jax-apiutils';
import { BehaviorSubject } from 'rxjs';

import { environment } from '../../environments/environment';

/** What `GET /api/sessions/me` reports. Never includes a token. */
export interface SessionState {
  /** Whether this environment offers sign-in at all. */
  loginAvailable: boolean;
  authenticated: boolean;
  email?: string | null;
  name?: string | null;
}

interface SessionsMeResponse {
  login_available: boolean;
  authenticated: boolean;
  email?: string | null;
  name?: string | null;
}

const SIGNED_OUT: SessionState = { loginAvailable: false, authenticated: false };

/**
 * Who is signed in, and how to sign in or out.
 *
 * Sign-in is server-side, like legacy GeneWeaver: the API is the Auth0 client, exchanges the
 * code with its client secret, and keeps the token in an encrypted `HttpOnly` cookie. So this
 * page never sees a token: signing in is a plain navigation to the API, signing out a form
 * POST to it (the API refuses a sign-out that does not come from this site), and the cookie
 * rides along with every `/api` call by itself, the page and API being one origin.
 */
@Injectable({ providedIn: 'root' })
export class SessionService {
  private api: ApiBaseService;

  /** `undefined` until the first answer, so the page can tell "unknown" from "signed out". */
  readonly state$ = new BehaviorSubject<SessionState | undefined>(undefined);

  constructor(apiBaseServiceFactory: ApiBaseServiceFactory) {
    this.api = apiBaseServiceFactory.create(environment.urls.geneWeaverApi);
    this.refresh();
  }

  get current(): SessionState | undefined {
    return this.state$.value;
  }

  get authenticated(): boolean {
    return !!this.current?.authenticated;
  }

  refresh(): void {
    this.api.get<SessionsMeResponse>('/sessions/me').subscribe({
      next: (response) => {
        const me = response.object;
        this.state$.next(
          me
            ? {
                loginAvailable: me.login_available,
                authenticated: me.authenticated,
                email: me.email,
                name: me.name,
              }
            : SIGNED_OUT,
        );
      },
      // An unreachable session endpoint is treated as signed out, not as an error page.
      error: () => this.state$.next(SIGNED_OUT),
    });
  }

  /** Where to send the browser to sign in, coming back to `returnPath` afterwards. */
  signInUrl(returnPath: string = window.location.pathname + window.location.search): string {
    return (
      `${environment.urls.geneWeaverApi}/sessions/login?next=` + encodeURIComponent(returnPath)
    );
  }

  /** The sign-out form's action. It must be POSTed from this page, not linked to. */
  signOutUrl(): string {
    return `${environment.urls.geneWeaverApi}/sessions/logout`;
  }
}
