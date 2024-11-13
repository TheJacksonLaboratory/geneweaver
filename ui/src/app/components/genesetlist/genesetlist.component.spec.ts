import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GeneSetListComponent } from './genesetlist.component';
import { CommonModule } from '@angular/common';
import { TableModule } from "primeng/table";
import { TagModule } from "primeng/tag";
import { Button } from "primeng/button";
import { TierTagComponent } from "../tiertag/tiertag.component";
import { Router } from '@angular/router';
import { GeneSet } from "../../models/gene-set";


describe('GeneSetListComponent', () => {
  let component: GeneSetListComponent;
  let fixture: ComponentFixture<GeneSetListComponent>;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GeneSetListComponent, CommonModule, TableModule, TagModule, Button, TierTagComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(GeneSetListComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

});