import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GeneSetListComponent } from './genesetlist.component';
import { CommonModule } from '@angular/common';
import { TableModule } from "primeng/table";
import { TagModule } from "primeng/tag";
import { Button } from "primeng/button";
import { TierTagComponent } from "../tiertag/tiertag.component";
import { GeneSet } from "../../models/gene-set";


describe('GeneSetListComponent', () => {
  let component: GeneSetListComponent;
  let fixture: ComponentFixture<GeneSetListComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GeneSetListComponent, CommonModule, TableModule, TagModule, Button, TierTagComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(GeneSetListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('expands a row to show its description, and collapses it again', async () => {
    // PrimeNG 18+ reads the expansion template only as "expandedrow"; under its old name
    // ("rowexpansion") the toggler did nothing.
    const geneset = { id: 430, name: 'EthanolWithdrawal', description: 'Genes changed in withdrawal' } as GeneSet;
    fixture.componentRef.setInput('geneSets', [geneset]);
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    const toggler = () => el.querySelector('tbody tr td:last-child button') as HTMLButtonElement;
    expect(el.textContent).not.toContain('Genes changed in withdrawal');

    toggler().click();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(el.textContent).toContain('Genes changed in withdrawal');
    expect(el.querySelector('.pi-chevron-down')).not.toBeNull();

    toggler().click();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(el.textContent).not.toContain('Genes changed in withdrawal');
  });

});