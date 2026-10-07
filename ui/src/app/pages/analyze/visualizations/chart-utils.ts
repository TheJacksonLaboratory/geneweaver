/**
 * The shared chart foundation G3-803 asks for, kept deliberately small: one palette, one
 * way to export, and SVG `<title>` tooltips (native, keyboard- and screen-reader-visible,
 * no tooltip library) on every mark that carries a number.
 */
import { interpolateBlues, scaleSequential, select, Selection } from 'd3';

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
    .attr('role', 'img')
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
