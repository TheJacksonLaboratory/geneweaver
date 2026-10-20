import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiBaseServiceFactory } from 'jax-apiutils';
import { Subscription } from 'rxjs';
import { AutoComplete, AutoCompleteModule } from 'primeng/autocomplete';

import { environment } from '../../../environments/environment';
import { GenesetOption, parseIds } from '../../search/geneset-options';
import { GenesetSearchSource } from '../../search/geneset-search-source';
import { emptyFilters, SearchFilters } from '../../search/search-filters';
import { LIST_HEIGHT, ROW_HEIGHT_PX, SUGGESTION_STYLES } from '../../search/suggestion-list';

/**
 * The gene sets to analyse: type to search them, or type and paste ids as before.
 *
 * Searches `GET /genesets/search`, which matches ids (`167180`, `GS167180`) and words from a
 * gene set's name, description and other metadata, and returns only gene sets the caller may
 * read. Results arrive a page at a time: scrolling to the end of the list fetches the next.
 * `filters` narrow them (G3-777, G3-764), as on the /next search page.
 *
 * Ids stay first-class. Typing or pasting `514, 515` and pressing Enter, a comma, or leaving
 * the field adds them without picking from the list -- once each is looked up: an id the user
 * may not read, or that does not exist, is reported and not added. (It used to be added as
 * typed, and the run then refused it: "Not authorized to read gene set(s): 51, 54".)
 *
 * Bound as `[(ids)]` to the page's list of id strings, so the page's own checks and its
 * other ways of filling the field (ABBA's "use these gene sets") are unchanged.
 */
@Component({
  selector: 'app-geneset-picker',
  standalone: true,
  imports: [CommonModule, FormsModule, AutoCompleteModule],
  styles: [SUGGESTION_STYLES],
  template: `
    <p-autoComplete
      [inputId]="inputId"
      [(ngModel)]="selected"
      (ngModelChange)="selectionChanged($event)"
      [suggestions]="source.suggestions"
      (completeMethod)="search($event.query)"
      [multiple]="true"
      [unique]="true"
      dataKey="id"
      optionLabel="chip"
      [delay]="300"
      [minLength]="1"
      [virtualScroll]="true"
      [virtualScrollItemSize]="rowHeight"
      [lazy]="true"
      (onLazyLoad)="source.loadMore($event.last)"
      [scrollHeight]="listHeight"
      [showEmptyMessage]="true"
      [emptyMessage]="emptyMessage"
      (onKeyUp)="keyUp($event)"
      (onBlur)="blur($event)"
      [placeholder]="selected.length ? '' : placeholder"
      [ariaLabel]="ariaLabel"
      styleClass="w-full"
      inputStyleClass="w-full"
    >
      <ng-template let-option pTemplate="item">
        <div class="geneset-option" [attr.data-gs-id]="option.id">
          <div class="white-space-nowrap overflow-hidden text-overflow-ellipsis">
            <strong>GS{{ option.id }}</strong>
            <span *ngIf="option.abbreviation" class="ml-2">{{ option.abbreviation }}</span>
          </div>
          <small *ngIf="option.detail" class="block text-color-secondary">{{ option.detail }}</small>
        </div>
      </ng-template>
    </p-autoComplete>
    <small *ngIf="source.loading" class="block mt-1 text-color-secondary" aria-live="polite">
      Searching gene sets…
    </small>
    <small *ngIf="source.failed" class="block mt-1 text-color-secondary" aria-live="polite">
      The gene set search is not responding. You can still type gene set IDs.
    </small>
    <small *ngIf="checking" class="block mt-1 text-color-secondary" aria-live="polite">
      Checking {{ checking }}…
    </small>
    <small *ngIf="rejected" class="block mt-1 text-orange-600 rejected-ids" aria-live="polite">
      {{ rejected }}
    </small>
  `,
})
export class GenesetPickerComponent implements OnChanges, OnDestroy {
  /** The selected gene set ids, as the page holds them. */
  @Input() ids: string[] = [];
  @Output() idsChange = new EventEmitter<string[]>();
  /** Narrow the suggestions, as on the search page. */
  @Input() filters: SearchFilters = emptyFilters();
  @Input() inputId = 'genesetIds';
  @Input() ariaLabel = 'Gene sets to analyze';
  @Input() placeholder = 'Search by name or ID, or type IDs, e.g. 514, 515';

  @ViewChild(AutoComplete) private autoComplete?: AutoComplete;

  readonly rowHeight = ROW_HEIGHT_PX;
  readonly listHeight = LIST_HEIGHT;
  readonly source: GenesetSearchSource;
  selected: GenesetOption[] = [];
  /** Typed ids still being looked up, and those refused since the user last chose. */
  private checkingIds = new Set<number>();
  private rejectedIds: number[] = [];
  private uncheckedIds: number[] = [];
  /** Every lookup runs to the end: typing "1, 2, 3" starts one per comma. */
  private lookups = new Subscription();

  constructor(apiBaseServiceFactory: ApiBaseServiceFactory) {
    this.source = new GenesetSearchSource(apiBaseServiceFactory.create(environment.urls.geneWeaverApi));
  }

  /** Typed ids being looked up, e.g. "GS51, GS54". */
  get checking(): string | undefined {
    return this.checkingIds.size ? [...this.checkingIds].map((id) => `GS${id}`).join(', ') : undefined;
  }

  /** Why some typed ids were not added. */
  get rejected(): string | undefined {
    const notes: string[] = [];
    if (this.rejectedIds.length) {
      notes.push(
        `Not added: ${this.rejectedIds.map((id) => `GS${id}`).join(', ')} -- no gene set you ` +
          'can read has that ID. It may be private to someone else, or not exist.',
      );
    }
    if (this.uncheckedIds.length) {
      notes.push(`Could not check ${this.uncheckedIds.map((id) => `GS${id}`).join(', ')}; try again.`);
    }
    return notes.join(' ') || undefined;
  }

  get emptyMessage(): string {
    return parseIds(this.source.currentQuery)
      ? 'No gene set you can read has that ID.'
      : 'No gene sets match. Try other words or filters, or type gene set IDs.';
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['ids']) {
      const current = this.selected.map((option) => String(option.id));
      if (current.join(',') !== (this.ids ?? []).join(',')) {
        this.selected = (this.ids ?? []).map((id) => this.optionFor(id));
      }
    }
    if (changes['filters'] && this.filters) {
      this.source.setFilters(this.filters);
    }
  }

  ngOnDestroy(): void {
    this.source.destroy();
    this.lookups.unsubscribe();
  }

  search(query: string): void {
    this.source.search(query);
  }

  /** The user changed the chips: earlier refusals no longer apply. */
  selectionChanged(options: GenesetOption[] | null): void {
    this.rejectedIds = [];
    this.uncheckedIds = [];
    this.setSelected(options);
  }

  private setSelected(options: GenesetOption[] | null): void {
    this.selected = options ?? [];
    this.selected.forEach((option) => this.source.known.set(option.id, option));
    this.idsChange.emit(this.selected.map((option) => String(option.id)));
  }

  /** Enter or a comma after ids adds them as typed, without choosing a suggestion. */
  keyUp(event: KeyboardEvent): void {
    if (event.key === 'Enter' || event.key === ',') {
      this.addTyped(event.target as HTMLInputElement);
    }
  }

  /** Leaving the field keeps ids typed into it, as the old chips field did. */
  blur(event: Event): void {
    this.addTyped(event.target as HTMLInputElement);
  }

  private addTyped(input: HTMLInputElement | null): void {
    const ids = input ? parseIds(input.value) : undefined;
    if (!input || !ids) {
      return;
    }
    const present = new Set([...this.selected.map((option) => option.id), ...this.checkingIds]);
    const typed = ids.filter((id) => !present.has(id) && present.add(id));
    input.value = '';
    this.source.reset();
    // The keystrokes that typed the ids started a debounced search; it would open the list
    // again for text that is no longer there. PrimeNG's hide() touches the list's scroller,
    // which exists only while the list is open.
    if (this.autoComplete) {
      clearTimeout(this.autoComplete.searchTimeout);
      if (this.autoComplete.overlayVisible) {
        this.autoComplete.hide();
      }
    }
    if (!typed.length) {
      return;
    }
    // Only what this user may read becomes a chip, as a run would refuse the rest.
    typed.forEach((id) => this.checkingIds.add(id));
    this.lookups.add(
      this.source.lookup(typed).subscribe((lookup) => {
        typed.forEach((id) => this.checkingIds.delete(id));
        const have = new Set(this.selected.map((option) => option.id));
        const added = lookup.found.filter((option) => !have.has(option.id));
        if (added.length) {
          this.setSelected([...this.selected, ...added]);
        }
        this.rejectedIds = [...new Set([...this.rejectedIds, ...lookup.unreadable])];
        this.uncheckedIds = [...new Set([...this.uncheckedIds, ...lookup.unchecked])];
      }),
    );
  }

  private optionFor(id: string): GenesetOption {
    const numeric = Number(id);
    return this.source.known.get(numeric) ?? { id: numeric, chip: Number.isInteger(numeric) ? `GS${id}` : id };
  }
}
