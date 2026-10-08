/**
 * The shared chart foundation G3-803 asks for, kept deliberately small: one palette, one
 * way to export, and one interactive tooltip used by every chart.
 *
 * The tooltip follows the pointer, and also opens on keyboard focus: every mark that
 * carries a number is focusable and labelled, so the charts are not mouse-only.
 */
import { BaseType, interpolateBlues, scaleSequential, select, Selection } from 'd3';

import { TooltipContent } from './models';

/** Bars, circles and graph nodes. Matches PrimeNG's primary blue. */
export const ACCENT = '#3B82F6';
export const MUTED = '#94A3B8';
export const HIGHLIGHT = '#DC2626';

/** Sequential scale for matrices: pale for low, dark for high. */
export function sequential(domain: [number, number]) {
  return scaleSequential(interpolateBlues).domain(domain);
}

/** Empty the host and start a fresh responsive SVG of the given drawing size. */
export function freshSvg(
  host: HTMLElement,
  width: number,
  height: number,
  label: string,
): Selection<SVGSVGElement, unknown, null, undefined> {
  select(host).selectAll('*').remove();
  return select(host)
    .append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('width', '100%')
    // A labelled group, not role="img": an image role makes every descendant presentational,
    // which would hide the focusable, labelled marks from assistive technology.
    .attr('role', 'group')
    .attr('aria-roledescription', 'chart')
    .attr('aria-label', label)
    .style('max-width', `${width}px`)
    .style('font', '11px sans-serif');
}

/** Save the chart as a standalone SVG file. */
export function downloadSvg(host: HTMLElement, filename: string): void {
  const svg = host.querySelector('svg');
  if (!svg) {
    return;
  }
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  const blob = new Blob([new XMLSerializer().serializeToString(clone)], {
    type: 'image/svg+xml',
  });
  saveBlob(blob, filename);
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

// --- interactive tooltip ---------------------------------------------------------------

export type { TooltipContent, TooltipRow } from './models';

/** The content as one line, for `aria-label`, so screen readers get what sighted users see. */
export function tooltipText(content: TooltipContent): string {
  const rows = (content.rows ?? []).map((row) => `${row.label}: ${row.value}`);
  return [content.title, ...rows, content.note].filter(Boolean).join('. ');
}

/**
 * A tooltip panel inside a chart's host element.
 *
 * Built with `textContent` only, never `innerHTML`: gene and gene set names come from the
 * database, and must not be able to inject markup.
 */
export class ChartTooltip {
  readonly element: HTMLDivElement;

  constructor(private host: HTMLElement) {
    host.style.position = 'relative';
    this.element = document.createElement('div');
    this.element.className = 'chart-tooltip';
    this.element.setAttribute('role', 'tooltip');
    Object.assign(this.element.style, {
      position: 'absolute',
      pointerEvents: 'none',
      zIndex: '10',
      maxWidth: '300px',
      padding: '6px 8px',
      borderRadius: '4px',
      background: '#0F172A',
      color: 'white',
      font: '12px sans-serif',
      lineHeight: '1.4',
      boxShadow: '0 2px 6px rgba(0,0,0,.25)',
      display: 'none',
    });
    host.appendChild(this.element);
  }

  get visible(): boolean {
    return this.element.style.display !== 'none';
  }

  /** Show `content` beside a pointer position, or beside an element when focused. */
  show(content: TooltipContent, at: MouseEvent | Element): void {
    this.element.replaceChildren();
    const title = document.createElement('div');
    title.style.fontWeight = '600';
    title.textContent = content.title;
    this.element.appendChild(title);
    for (const row of content.rows ?? []) {
      const line = document.createElement('div');
      const label = document.createElement('span');
      label.style.opacity = '0.75';
      label.textContent = `${row.label}: `;
      const value = document.createElement('span');
      value.textContent = row.value;
      line.append(label, value);
      this.element.appendChild(line);
    }
    if (content.note) {
      const note = document.createElement('div');
      note.style.marginTop = '4px';
      note.style.opacity = '0.75';
      note.textContent = content.note;
      this.element.appendChild(note);
    }
    this.element.style.display = 'block';
    this.move(at);
  }

  move(at: MouseEvent | Element): void {
    const box = this.host.getBoundingClientRect();
    let x: number;
    let y: number;
    if (at instanceof Element) {
      const target = at.getBoundingClientRect();
      x = target.right - box.left;
      y = target.top - box.top;
    } else {
      x = at.clientX - box.left;
      y = at.clientY - box.top;
    }
    // Flip to the left of the pointer near the host's right edge, so it is never cut off.
    const width = this.element.offsetWidth || 200;
    const left = x + 14 + width > box.width ? Math.max(0, x - 14 - width) : x + 14;
    this.element.style.left = `${left}px`;
    this.element.style.top = `${Math.max(0, y + 12)}px`;
  }

  hide(): void {
    this.element.style.display = 'none';
  }
}

/**
 * Make each mark in `marks` show `content(datum)` on hover and on keyboard focus, and run
 * `highlight(datum)` / `clear()` alongside -- the chart decides what "related" means.
 */
export function interactive<E extends BaseType, D, P extends BaseType>(
  marks: Selection<E, D, P, unknown>,
  tooltip: ChartTooltip,
  content: (datum: D) => TooltipContent,
  highlight?: (datum: D) => void,
  clear?: () => void,
): void {
  marks
    .attr('tabindex', 0)
    .attr('focusable', 'true')
    .attr('aria-label', (datum) => tooltipText(content(datum)))
    .classed('chart-mark', true)
    .style('cursor', 'pointer')
    .on('mouseenter', (event, datum) => {
      tooltip.show(content(datum), event as MouseEvent);
      highlight?.(datum);
    })
    .on('mousemove', (event) => tooltip.move(event as MouseEvent))
    .on('mouseleave', () => {
      tooltip.hide();
      clear?.();
    })
    .on('focus', function (_event, datum) {
      tooltip.show(content(datum), this as Element);
      highlight?.(datum);
    })
    .on('blur', () => {
      tooltip.hide();
      clear?.();
    });
}

/** Opacity for marks that are not part of what is highlighted. */
export const DIMMED = 0.2;

export function percent(part: number, whole: number): string {
  return whole > 0 ? `${((part / whole) * 100).toFixed(1)}%` : '—';
}
