/**
 * How a gene set suggestion list is drawn, shared by the analyze picker and the /next search
 * field so both lists look and scroll alike.
 */

/**
 * Every suggestion is one fixed-height row of two lines. The virtual scroller positions rows
 * by this size, so it must match what is drawn -- `SUGGESTION_STYLES` pins it.
 */
export const ROW_HEIGHT_PX = 52;

/** Rows the list shows without scrolling. */
export const VISIBLE_ROWS = 10;

/** The list's own top and bottom padding (PrimeNG's 0.25rem each). */
const LIST_PADDING_PX = 8;

/** Tall enough for ten suggestions; more scroll, and load as they come into view. */
export const LIST_HEIGHT = `${VISIBLE_ROWS * ROW_HEIGHT_PX + LIST_PADDING_PX}px`;

/**
 * - The field fills its column.
 * - Rows are exactly `ROW_HEIGHT_PX` (52px) with no margin, so the virtual scroller's row
 *   positions match what is drawn.
 * - The virtual list's content otherwise grows to its longest name, wider than the panel, and
 *   long names are clipped at its edge instead of ending in an ellipsis.
 * - A long gene set name is cut short on its chip rather than wrapping it onto two lines.
 */
export const SUGGESTION_STYLES = `
  :host ::ng-deep .p-autocomplete,
  :host ::ng-deep .p-autocomplete-multiple-container,
  :host ::ng-deep .p-autocomplete-input {
    width: 100%;
  }
  :host ::ng-deep .p-autocomplete-panel .p-autocomplete-item {
    height: 52px;
    margin: 0;
    overflow: hidden;
  }
  :host ::ng-deep .p-autocomplete-panel .p-scroller-content {
    width: 100%;
  }
  :host ::ng-deep .p-autocomplete-token-label {
    max-width: 18rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
`;
