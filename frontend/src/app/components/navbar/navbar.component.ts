import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SystemStatus } from '../../models/talentagent.models';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <header class="navbar glass-panel">
      <div class="brand-section">
        <div class="brand-logo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <div>
          <div class="brand-title">TalentAgent</div>
          <div class="brand-subtitle">Autonomous Job Search & Application System</div>
        </div>
      </div>

      <nav class="nav-tabs">
        <button
          class="tab-btn"
          [class.active]="activeTab === 'profile'"
          (click)="selectTab('profile')"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
          Candidate Profile
        </button>

        <button
          class="tab-btn"
          [class.active]="activeTab === 'compose'"
          (click)="selectTab('compose')"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          Apply & Compose
        </button>

        <button
          class="tab-btn"
          [class.active]="activeTab === 'graph'"
          (click)="selectTab('graph')"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="18" cy="5" r="3"/>
            <circle cx="6" cy="12" r="3"/>
            <circle cx="18" cy="19" r="3"/>
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
          </svg>
          Evidence Graph
        </button>

        <button
          class="tab-btn"
          [class.active]="activeTab === 'guardrails'"
          (click)="selectTab('guardrails')"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          System & Guardrails
        </button>
      </nav>

      <div class="system-pills">
        <div class="pill-quota" *ngIf="status">
          <span class="quota-label">Flash Tier 2:</span>
          <span class="quota-val">{{ status.quotas.tier_2_used }} / {{ status.quotas.tier_2_limit }}</span>
        </div>

        <div class="badge badge-guardrail">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          G1-G7 Enforced
        </div>

        <div class="status-indicator" [class.connected]="isConnected">
          <span class="status-dot"></span>
          {{ isConnected ? 'Live Backend' : 'Offline Session' }}
        </div>
      </div>
    </header>
  `,
  styles: [`
    .navbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 24px;
      margin: 16px 24px;
      border-radius: 12px;
      gap: 16px;
    }
    .brand-section {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-logo {
      width: 40px;
      height: 40px;
      border-radius: 10px;
      background: linear-gradient(135deg, #14b8a6, #3b82f6);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #ffffff;
    }
    .brand-title {
      font-size: 1.125rem;
      font-weight: 700;
      color: var(--text-primary);
      letter-spacing: -0.01em;
    }
    .brand-subtitle {
      font-size: 0.75rem;
      color: var(--text-secondary);
    }
    .nav-tabs {
      display: flex;
      align-items: center;
      gap: 6px;
      background: rgba(0, 0, 0, 0.3);
      padding: 4px;
      border-radius: 10px;
      border: 1px solid var(--border-subtle);
    }
    .tab-btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 14px;
      border-radius: 8px;
      background: transparent;
      border: none;
      color: var(--text-secondary);
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .tab-btn:hover {
      color: var(--text-primary);
      background: rgba(255, 255, 255, 0.05);
    }
    .tab-btn.active {
      color: #ffffff;
      background: #1f293d;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    }
    .system-pills {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .pill-quota {
      font-size: 0.75rem;
      background: var(--bg-dark);
      padding: 4px 10px;
      border-radius: 6px;
      border: 1px solid var(--border-subtle);
    }
    .quota-label {
      color: var(--text-muted);
      margin-right: 4px;
    }
    .quota-val {
      color: var(--accent-amber);
      font-family: var(--font-mono);
      font-weight: 600;
    }
    .status-indicator {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.75rem;
      color: var(--text-secondary);
      padding: 4px 8px;
      background: var(--bg-dark);
      border-radius: 6px;
      border: 1px solid var(--border-subtle);
    }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #f59e0b;
    }
    .status-indicator.connected .status-dot {
      background: #10b981;
      box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
    }
  `],
})
export class NavbarComponent {
  @Input() activeTab: string = 'profile';
  @Input() status: SystemStatus | null = null;
  @Input() isConnected: boolean = false;
  @Output() tabChange = new EventEmitter<string>();

  selectTab(tab: string): void {
    this.tabChange.emit(tab);
  }
}
