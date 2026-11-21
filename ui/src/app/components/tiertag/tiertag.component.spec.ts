import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TierTagComponent } from './tiertag.component';
import { TagModule } from 'primeng/tag';

describe('TierTagComponent', () => {
  let component: TierTagComponent;
  let fixture: ComponentFixture<TierTagComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TierTagComponent, TagModule],
    }).compileComponents();

    fixture = TestBed.createComponent(TierTagComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  describe('Input handling', () => {
    it('should have default tier value of 5', () => {
      expect(component.tier()).toBe(5);
    });

    it('should accept tier input values', () => {
      fixture.componentRef.setInput('tier', 2);
      expect(component.tier()).toBe(2);
    });
  });

  describe('getTierLabel', () => {
    it('should return correct label for Tier I', () => {
      fixture.componentRef.setInput('tier', 1);
      expect(component.getTierLabel()).toBe('Tier I');
    });

    it('should return correct label for Tier III', () => {
      fixture.componentRef.setInput('tier', 3);
      expect(component.getTierLabel()).toBe('Tier III');
    });

    it('should return correct label for Tier V', () => {
      fixture.componentRef.setInput('tier', 5);
      expect(component.getTierLabel()).toBe('Tier V');
    });

    it('should handle all possible tier values', () => {
      const expectedLabels = ['Tier I', 'Tier II', 'Tier III', 'Tier IV', 'Tier V'];

      for (let i = 1; i <= 5; i++) {
        fixture.componentRef.setInput('tier', i);
        expect(component.getTierLabel()).toBe(expectedLabels[i - 1]);
      }
    });
  });

  describe('getTierColor', () => {
    it('should return success color for Tier I', () => {
      fixture.componentRef.setInput('tier', 1);
      expect(component.getTierColor()).toBe('success');
    });

    it('should return info color for Tier II', () => {
      fixture.componentRef.setInput('tier', 2);
      expect(component.getTierColor()).toBe('info');
    });

    it('should return the warn color for Tier III (PrimeNG 18+ name)', () => {
      fixture.componentRef.setInput('tier', 3);
      expect(component.getTierColor()).toBe('warn');
    });

    it('should return danger color for Tier IV', () => {
      fixture.componentRef.setInput('tier', 4);
      expect(component.getTierColor()).toBe('danger');
    });

    it('should return secondary color for Tier V', () => {
      fixture.componentRef.setInput('tier', 5);
      expect(component.getTierColor()).toBe('secondary');
    });

    it('should handle all possible tier values', () => {
      const expectedColors = ['success', 'info', 'warn', 'danger', 'secondary'];

      for (let i = 1; i <= 5; i++) {
        fixture.componentRef.setInput('tier', i);
        expect(component.getTierColor()).toBe(expectedColors[i - 1]);
      }
    });
  });

  describe('Edge cases', () => {
    it('should handle out-of-range tier values gracefully', () => {
      // Test values outside valid range
      fixture.componentRef.setInput('tier', 0);
      expect(component.getTierLabel()).toBeUndefined();
      expect(component.getTierColor()).toBeUndefined();

      fixture.componentRef.setInput('tier', 6);
      expect(component.getTierLabel()).toBeUndefined();
      expect(component.getTierColor()).toBeUndefined();
    });
  });

  // Template integration tests
  describe('Template integration', () => {
    it('should render the correct tier label in the template', () => {
      fixture.componentRef.setInput('tier', 1);
      fixture.detectChanges();

      expect(component.tier()).toBe(1);

    });

    // Note: Additional template tests would depend on the actual HTML template
    // Once you provide the template content, we can add more specific tests
  });
});