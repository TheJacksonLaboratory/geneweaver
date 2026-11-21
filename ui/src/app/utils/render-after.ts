import { ChangeDetectorRef } from '@angular/core';
import { MonoTypeOperatorFunction, Observable } from 'rxjs';

/**
 * Pass a stream through, then mark the component for checking after each value, error or
 * completion has been handled.
 *
 * The app runs without zone.js (zoneless change detection), so Angular no longer re-renders
 * after an HTTP response or a route change by itself: a template event, a signal or
 * `markForCheck` has to say the view changed. Components whose state is plain fields set in
 * a subscription put this before `.subscribe(...)`, so the subscriber's assignments are made
 * first and the view is then checked once.
 */
export function renderAfter<T>(changes: ChangeDetectorRef): MonoTypeOperatorFunction<T> {
  return (source) =>
    new Observable<T>((subscriber) =>
      source.subscribe({
        next: (value) => {
          subscriber.next(value);
          changes.markForCheck();
        },
        error: (error) => {
          subscriber.error(error);
          changes.markForCheck();
        },
        complete: () => {
          subscriber.complete();
          changes.markForCheck();
        },
      }),
    );
}
