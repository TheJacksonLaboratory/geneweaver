import { TestBed } from '@angular/core/testing';
import { ApiBaseServiceFactory } from 'jax-apiutils';
import { of, throwError, Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { SessionService } from './session.service';

describe('SessionService', () => {
  let me: () => Observable<unknown>;

  const build = () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        {
          provide: ApiBaseServiceFactory,
          useValue: { create: () => ({ get: () => me() }) } as unknown as ApiBaseServiceFactory,
        },
      ],
    });
    return TestBed.inject(SessionService);
  };

  it('reports a signed-in user', () => {
    me = () =>
      of({
        object: { login_available: true, authenticated: true, email: 'a@jax.org', name: 'A' },
      });
    const service = build();
    expect(service.authenticated).toBe(true);
    expect(service.current).toEqual({
      loginAvailable: true,
      authenticated: true,
      email: 'a@jax.org',
      name: 'A',
    });
  });

  it('reports signed out', () => {
    me = () => of({ object: { login_available: true, authenticated: false } });
    expect(build().authenticated).toBe(false);
  });

  it('treats an unreachable session endpoint as signed out, not as an error', () => {
    me = () => throwError(() => ({ status: 0 }));
    const service = build();
    expect(service.current).toEqual({ loginAvailable: false, authenticated: false });
  });

  it('signs in through the API, returning to the given page', () => {
    me = () => of({ object: {} });
    expect(build().signInUrl('/next/analyze?x=1')).toBe(
      `${environment.urls.geneWeaverApi}/sessions/login?next=%2Fnext%2Fanalyze%3Fx%3D1`,
    );
  });

  it('signs out through the API', () => {
    me = () => of({ object: {} });
    expect(build().signOutUrl()).toBe(`${environment.urls.geneWeaverApi}/sessions/logout`);
  });
});
