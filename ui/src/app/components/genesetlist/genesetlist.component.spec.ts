import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GeneSetListComponent } from './genesetlist.component';
import { CommonModule } from '@angular/common';
import { TableModule } from "primeng/table";
import { TagModule } from "primeng/tag";
import { Button } from "primeng/button";
import { TierTagComponent } from "../tiertag/tiertag.component";


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

});