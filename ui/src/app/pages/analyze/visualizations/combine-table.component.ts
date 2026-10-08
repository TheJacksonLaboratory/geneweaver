import { NgFor } from '@angular/common';
import { ChangeDetectionStrategy, Component, Input, OnChanges } from '@angular/core';
import { TableModule } from 'primeng/table';

import { combineModel, CombineModel } from './models';

/** Combine: every gene against every gene set, most widely shared genes first. */
@Component({
  selector: 'app-combine-table',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgFor, TableModule],
  template: `
    <p class="text-sm text-color-secondary mt-0">
      {{ model.rows.length }} genes across {{ model.columns.length }} gene sets.
    </p>
    <p-table [value]="model.rows" styleClass="p-datatable-sm" [scrollable]="true" scrollHeight="420px">
      <ng-template pTemplate="header">
        <tr>
          <th>Gene</th>
          <th *ngFor="let column of model.columns" [title]="column.label">GS{{ column.id }}</th>
          <th>In</th>
        </tr>
      </ng-template>
      <ng-template pTemplate="body" let-row>
        <tr>
          <td>{{ row.gene }}</td>
          <td *ngFor="let column of model.columns" class="text-center">
            {{ row.members[column.id] ? '●' : '' }}
          </td>
          <td>{{ row.count }}</td>
        </tr>
      </ng-template>
    </p-table>
  `,
})
export class CombineTableComponent implements OnChanges {
  @Input({ required: true }) result!: Parameters<typeof combineModel>[0];
  model: CombineModel = { columns: [], rows: [] };

  ngOnChanges(): void {
    this.model = combineModel(this.result);
  }
}
