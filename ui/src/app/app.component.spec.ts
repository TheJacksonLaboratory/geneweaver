import { TestBed } from '@angular/core/testing';
import { AppComponent } from './app.component';
import { RouterModule } from '@angular/router';
import { BehaviorSubject } from 'rxjs';
import { SessionService } from './services/session.service';

describe('AppComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent, RouterModule.forRoot([])],
      providers: [
        {
          provide: SessionService,
          useValue: {
            state$: new BehaviorSubject({ loginAvailable: true, authenticated: false }),
            signInUrl: () => '/api/sessions/login',
            signOutUrl: () => '/api/sessions/logout',
          },
        },
      ],
    }).compileComponents();
  });

  it(`should have as title 'Geneweaver'`, () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    expect(app.title).toEqual('Geneweaver');
  });

  it('offers sign-in when signed out', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const link = fixture.nativeElement.querySelector('a[href="/api/sessions/login"]');
    expect(link?.textContent).toContain('Sign in');
  });
});
