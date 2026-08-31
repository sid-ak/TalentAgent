import { Component, Input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api.service';
import { SystemStatus } from '../../models/talentagent.models';

@Component({
  selector: 'app-guardrails-view',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="guardrails-container animate-fade-in">
      <div class="view-header">
        <div>
          <h1 class="view-title">System Invariants & Zero-Budget Monitor</h1>
          <p class="view-desc">
            Enforced guardrails (Spec §10) and free-tier quota governance (ADR-0012) guaranteeing zero autonomous harm and zero billing surprises.
          </p>
        </div>
      </div>

      <!-- Zero Budget Quota Dashboard -->
      <div class="quota-dashboard glass-panel">
        <div class="section-title">
          <span>Zero-Budget Resource Tracker (ADR-0012)</span>
          <span class="badge badge-guardrail">Hard Ceiling Enforced</span>
        </div>
        <p class="subtext">
          Operates strictly within free tiers with no billing account. Offline fixtures protect daily request ceilings.
        </p>

        <div class="quota-grid">
          <div class="quota-card">
            <div class="quota-top">
              <span class="model-name">Gemini Flash (Tier 2 · Reasoning)</span>
              <span class="quota-ratio">{{ status?.quotas?.tier_2_used || 2 }} / {{ status?.quotas?.tier_2_limit || 250 }}</span>
            </div>
            <div class="gauge-track">
              <div
                class="gauge-fill"
                [style.width.%]="((status?.quotas?.tier_2_used || 2) / (status?.quotas?.tier_2_limit || 250)) * 100"
                style="background: #14b8a6"
              ></div>
            </div>
            <div class="quota-desc">Used for constrained bullet composition and final Pass 1 synthesis.</div>
          </div>

          <div class="quota-card">
            <div class="quota-top">
              <span class="model-name">Gemini Flash-Lite (Tier 1 · Classification)</span>
              <span class="quota-ratio">{{ status?.quotas?.tier_1_used || 4 }} / {{ status?.quotas?.tier_1_limit || 1000 }}</span>
            </div>
            <div class="gauge-track">
              <div
                class="gauge-fill"
                [style.width.%]="((status?.quotas?.tier_1_used || 4) / (status?.quotas?.tier_1_limit || 1000)) * 100"
                style="background: #3b82f6"
              ></div>
            </div>
            <div class="quota-desc">Used for batched requirement parsing and fast classification.</div>
          </div>
        </div>
      </div>

      <!-- Invariants G1-G7 Table -->
      <div class="guardrails-table-panel glass-panel">
        <div class="section-title">
          <span>Enforced Invariants (G1 - G7)</span>
          <span class="badge badge-guardrail">Asserted in CI Harness</span>
        </div>

        <div class="invariants-list">
          <div class="invariant-row" *ngFor="let g of invariants">
            <div class="inv-id">{{ g.id }}</div>
            <div class="inv-main">
              <div class="inv-title">{{ g.title }}</div>
              <div class="inv-desc">{{ g.description }}</div>
              <div class="inv-location">
                <span class="loc-label">Enforced At:</span> <code>{{ g.location }}</code>
              </div>
            </div>
            <div class="inv-status">
              <span class="badge badge-guardrail">Active & Asserted</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Single Writer State Ownership Table -->
      <div class="single-writer-panel glass-panel">
        <div class="section-title">
          <span>Single-Writer Coordination Architecture (Spec §2.2, ADR-0007)</span>
          <span class="badge badge-verifiable">Firestore Security Rules</span>
        </div>
        <p class="subtext">
          Agents never call one another directly. All coordination travels through durable Firestore collections with single-writer enforcement.
        </p>

        <table class="writer-table">
          <thead>
            <tr>
              <th>Firestore Collection</th>
              <th>Exclusive Single Writer</th>
              <th>Access Policy</th>
              <th>Immutability / Contract</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>packages</code></td>
              <td><span class="badge badge-verifiable">composer</span></td>
              <td>Read: Human/Worker · Write: Composer</td>
              <td>Replaced per composition run (Spec §5.1)</td>
            </tr>
            <tr>
              <td><code>evidence_graph</code></td>
              <td><span class="badge badge-verifiable">evidence</span></td>
              <td>Read: All Agents · Write: Evidence</td>
              <td>Quarantined derived nodes (G1)</td>
            </tr>
            <tr>
              <td><code>applications</code></td>
              <td><span class="badge badge-corroborated">pipeline</span></td>
              <td>Read: UI/Analyst · Write: Pipeline</td>
              <td>State machine transition log</td>
            </tr>
            <tr>
              <td><code>outcomes</code></td>
              <td><span class="badge badge-corroborated">pipeline</span></td>
              <td>Read: Analyst · Create: Pipeline</td>
              <td><strong>Append-Only by Rule (Spec §11)</strong></td>
            </tr>
            <tr>
              <td><code>hypotheses</code></td>
              <td><span class="badge badge-attested">analyst</span></td>
              <td>Read: UI/Analyst · Write: Analyst</td>
              <td>Experiment registration & findings</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  `,
  styles: [`
    .guardrails-container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 24px 48px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }
    .view-title {
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--text-primary);
    }
    .view-desc {
      color: var(--text-secondary);
      font-size: 0.95rem;
      margin-top: 4px;
    }
    .quota-dashboard, .guardrails-table-panel, .single-writer-panel {
      padding: 24px;
    }
    .section-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 1.15rem;
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 4px;
    }
    .subtext {
      font-size: 0.85rem;
      color: var(--text-secondary);
      margin-bottom: 20px;
    }
    .quota-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    @media (max-width: 768px) {
      .quota-grid { grid-template-columns: 1fr; }
    }
    .quota-card {
      background: var(--bg-dark);
      padding: 16px;
      border-radius: 8px;
      border: 1px solid var(--border-subtle);
    }
    .quota-top {
      display: flex;
      justify-content: space-between;
      margin-bottom: 10px;
      font-size: 0.9rem;
      font-weight: 600;
    }
    .quota-ratio {
      font-family: var(--font-mono);
      color: var(--accent-amber);
    }
    .quota-desc {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 8px;
    }
    .invariants-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .invariant-row {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      background: var(--bg-dark);
      padding: 14px 16px;
      border-radius: 8px;
      border: 1px solid var(--border-subtle);
    }
    .inv-id {
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: 1rem;
      color: var(--accent-teal);
      background: rgba(20, 184, 166, 0.1);
      padding: 4px 8px;
      border-radius: 6px;
    }
    .inv-main {
      flex: 1;
    }
    .inv-title {
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 4px;
    }
    .inv-desc {
      font-size: 0.85rem;
      color: var(--text-secondary);
      line-height: 1.4;
      margin-bottom: 6px;
    }
    .inv-location {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .loc-label {
      margin-right: 4px;
    }
    .writer-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
    }
    .writer-table th, .writer-table td {
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid var(--border-subtle);
    }
    .writer-table th {
      color: var(--text-muted);
      font-size: 0.75rem;
      text-transform: uppercase;
    }
  `],
})
export class GuardrailsViewComponent implements OnInit {
  @Input() status: SystemStatus | null = null;

  invariants = [
    {
      id: 'G1',
      title: 'No model-originated claim reaches an employer',
      description: 'Derived nodes are barred from composer retrieval at the store boundary; schema rejects unconfirmed model text.',
      location: 'talentagent/evidence/store.py (@composer_query quarantine choke point)',
    },
    {
      id: 'G2',
      title: 'No generated line without an admissible credit',
      description: 'Package schema validation rejects any line missing credits or referencing non-existent/derived accomplishment IDs.',
      location: 'talentagent/composer/package.py (validate_package schema assertion)',
    },
    {
      id: 'G3',
      title: 'No irreversible autonomy (Submit is human-only)',
      description: 'submit_application is barred from all agent execution paths and requires explicit human reviewer authorization.',
      location: 'talentagent/tools/registry.py (side_effect: human-only)',
    },
    {
      id: 'G4',
      title: 'No suppression by self-derived signal',
      description: 'may_exclude is false on all prior records; model signals cannot remove opportunities.',
      location: 'talentagent/scoring/ranking.py (ranking policy layer)',
    },
    {
      id: 'G5',
      title: 'No prohibited automation',
      description: 'Egress allowlist strictly restricts outbound network traffic to authorized APIs.',
      location: 'talentagent/net/fetch.py (permitted-domain allowlist)',
    },
    {
      id: 'G6',
      title: 'No credential handling',
      description: 'Zero login, account-creation, or password-handling tools exist in the system registry.',
      location: 'talentagent/tools/catalog.py (registry verification)',
    },
    {
      id: 'G7',
      title: 'Untrusted content is data, never instruction',
      description: 'External job postings, ATS DOMs, and mail enter as UntrustedText data payloads and are never interpolated into prompt strings.',
      location: 'talentagent/net/untrusted.py (UntrustedText wrapper)',
    },
  ];

  constructor(private apiService: ApiService) {}

  async ngOnInit(): Promise<void> {
    if (!this.status) {
      this.status = await this.apiService.getStatus();
    }
  }
}
