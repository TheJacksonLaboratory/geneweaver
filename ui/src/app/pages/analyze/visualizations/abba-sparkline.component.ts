import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { select } from 'd3';

import { SparkBar, sparklineSummary } from './abba-models';
import { ChartTooltip, tooltipText } from './chart-utils';

const WIDTH = 80;
const HEIGHT = 26;
/** A zero still gets a short dash on the baseline, as legacy's sparklines drew it. */
const ZERO_HEIGHT = 1.5;

/**
 * One of ABBA's per-gene sparklines: gene sets by curation tier, or by species.
 *
 * Each bar has its own tooltip on hover. For the keyboard, the sparkline is one tab stop,
 * not one per bar -- 50 rows of 15 bars would be 750 stops -- and focusing it shows every
 * bar's count at once, which is also what its `aria-label` reads.
 */
@Component({
  selector: 'app-abba-sparkline',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div #host class="inline-block"></div>`,
})
export class AbbaSparklineComponent implements AfterViewInit, OnChanges {
  @Input({ required: true }) bars!: SparkBar[];
  /** What the bars count, e.g. "Gene sets by curation tier" -- the tooltip's title. */
  @Input({ required: true }) title!: string;
  @ViewChild('host', { static: true }) host!: ElementRef<HTMLDivElement>;

  private ready = false;

  ngAfterViewInit(): void {
    this.ready = true;
    this.draw();
  }

  ngOnChanges(): void {
    if (this.ready) {
      this.draw();
    }
  }

  private draw(): void {
    const host = this.host.nativeElement;
    select(host).selectAll('*').remove();
    const tooltip = new ChartTooltip(host);
    const summary = sparklineSummary(this.title, this.bars);
    const step = WIDTH / Math.max(this.bars.length, 1);
    const barWidth = Math.max(2, step * 0.7);

    const svg = select(host)
      .append('svg')
      .attr('width', WIDTH)
      .attr('height', HEIGHT)
      .attr('viewBox', `0 0 ${WIDTH} ${HEIGHT}`)
      .attr('role', 'img')
      .attr('tabindex', 0)
      .attr('aria-label', tooltipText(summary))
      .style('display', 'block')
      .style('cursor', 'default')
      .on('focus', function () {
        tooltip.show(summary, this as Element);
      })
      .on('blur', () => tooltip.hide());

    svg
      .selectAll('rect')
      .data(this.bars)
      .join('rect')
      .attr('class', 'spark-bar')
      .attr('x', (_bar, index) => index * step + (step - barWidth) / 2)
      .attr('width', barWidth)
      .attr('y', (bar) => HEIGHT - this.barHeight(bar))
      .attr('height', (bar) => this.barHeight(bar))
      .attr('fill', (bar) => bar.color)
      .on('mouseenter', (event, bar) =>
        tooltip.show(
          { title: bar.label, rows: [{ label: 'Gene sets', value: bar.count.toLocaleString() }] },
          event as MouseEvent,
        ),
      )
      .on('mousemove', (event) => tooltip.move(event as MouseEvent))
      .on('mouseleave', () => tooltip.hide());
  }

  private barHeight(bar: SparkBar): number {
    return bar.count > 0 ? Math.max(ZERO_HEIGHT + 1, bar.height * HEIGHT) : ZERO_HEIGHT;
  }
}
