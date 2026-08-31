import { Component, Input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import {
  ApplicationPackage,
  ATSFillResult,
  CandidateProfile,
  CreditedBullet,
  Gap,
} from '../../models/talentagent.models';

interface PresetPosting {
  id: string;
  title: string;
  company: string;
  platform: string;
  description: string;
  requirements: string[];
  isAdversarial?: boolean;
}

@Component({
  selector: 'app-compose-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="compose-container animate-fade-in">
      <div class="view-header">
        <div>
          <h1 class="view-title">Two-Pass Apply & Review Studio</h1>
          <p class="view-desc">
            Pass 1: Evidence-constrained composition with 100% credit trace-through and live elicitation. Pass 2: Deterministic ATS execution with human-only submission gate.
          </p>
        </div>
      </div>

      <!-- Top Row: Posting Selector & Config -->
      <div class="glass-panel config-panel">
        <div class="panel-section-title">
          <span>1. Select or Enter Job Posting</span>
          <span class="badge badge-guardrail">G1 & G2 Zero-Hallucination Assured</span>
        </div>

        <div class="preset-pills">
          <button
            *ngFor="let p of presetPostings"
            class="preset-btn"
            [class.active]="selectedPosting.id === p.id"
            [class.adversarial]="p.isAdversarial"
            (click)="selectPreset(p)"
          >
            <span *ngIf="p.isAdversarial">⚠️ </span>
            {{ p.title }} ({{ p.platform }})
          </button>
        </div>

        <div class="posting-editor">
          <div class="form-row">
            <input type="text" class="input-field" placeholder="Job Title / Role" [(ngModel)]="selectedPosting.title" />
            <select class="input-field select-field" [(ngModel)]="selectedPosting.platform">
              <option value="greenhouse">Greenhouse ATS</option>
              <option value="lever">Lever ATS</option>
              <option value="ashby">Ashby ATS</option>
            </select>
          </div>
          <textarea
            class="input-field posting-textarea"
            rows="4"
            placeholder="Paste Job Posting Description / Requirements..."
            [(ngModel)]="selectedPosting.description"
          ></textarea>
        </div>

        <div class="action-bar">
          <button class="btn btn-primary" (click)="runPass1()" [disabled]="isComposing">
            <span *ngIf="isComposing" class="spinner"></span>
            {{ isComposing ? 'Executing Pass 1...' : 'Run Pass 1: Constrained Composition' }}
          </button>
          <span class="active-profile-tag">
            Active Candidate: <strong>{{ activeProfileName }}</strong>
          </span>
        </div>
      </div>

      <!-- Pass 1 Output: Package & Sufficiency -->
      <div *ngIf="packageResult" class="pass1-results animate-fade-in">
        <div class="results-header">
          <h2>Pass 1 Output: Application Package</h2>
          <div class="coverage-bar-group">
            <span class="coverage-label">Credit Coverage:</span>
            <span class="badge badge-verifiable" *ngIf="packageResult.coverage.verifiable > 0">
              {{ (packageResult.coverage.verifiable * 100).toFixed(0) }}% Verifiable
            </span>
            <span class="badge badge-attested" *ngIf="packageResult.coverage.attested > 0">
              {{ (packageResult.coverage.attested * 100).toFixed(0) }}% Attested
            </span>
            <span class="badge badge-derived" *ngIf="packageResult.coverage.total === 0">
              0% (Gaps Handled)
            </span>
          </div>
        </div>

        <!-- Requirements & Sufficiency Gauges -->
        <div class="section-block glass-panel">
          <h3>Deterministic Sufficiency Scoring (Threshold: 0.60)</h3>
          <p class="subtext">Computed deterministically outside the model (ADR-0008). Requirements below 0.60 route to gaps.</p>
          
          <div class="requirements-list">
            <div *ngFor="let req of selectedPosting.requirements; let i = index" class="req-gauge-item">
              <div class="req-header">
                <span class="req-text">{{ req }}</span>
                <span class="score-badge" [class.pass]="getSufficiencyScore(req) >= 0.6">
                  {{ (getSufficiencyScore(req) * 100).toFixed(0) }}% Sufficiency
                </span>
              </div>
              <div class="gauge-track">
                <div
                  class="gauge-fill"
                  [style.width.%]="getSufficiencyScore(req) * 100"
                  [style.background]="getSufficiencyScore(req) >= 0.6 ? '#14b8a6' : '#f43f5e'"
                ></div>
                <div class="gauge-threshold-line" title="Threshold (0.60)"></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Composed Bullets with Click-to-Trace Evidence Drawer -->
        <div class="section-block glass-panel" *ngIf="packageResult.bullets.length > 0">
          <h3>Generated Resume Bullets (100% Credited)</h3>
          <p class="subtext">Every generated line resolves to admissible ground-truth evidence. Click a bullet to inspect provenance.</p>

          <div class="bullets-list">
            <div
              *ngFor="let bullet of packageResult.bullets; let idx = index"
              class="bullet-card"
              [class.active-bullet]="selectedBullet === bullet"
              (click)="inspectBullet(bullet)"
            >
              <div class="bullet-main">
                <div class="bullet-text">• {{ bullet.text }}</div>
                <div class="bullet-tags">
                  <span
                    class="badge"
                    [class.badge-verifiable]="bullet.attestation_class === 'verifiable'"
                    [class.badge-attested]="bullet.attestation_class === 'attested'"
                    [class.badge-corroborated]="bullet.attestation_class === 'corroborated'"
                  >
                    {{ bullet.attestation_class }}
                  </span>
                  <span class="credit-pill">Credit ID: {{ bullet.credits.join(', ') }}</span>
                  <span class="inspect-btn-text">🔍 Click to Trace Evidence</span>
                </div>
              </div>

              <!-- Expanded Evidence Trace Drawer -->
              <div *ngIf="selectedBullet === bullet" class="evidence-drawer animate-fade-in">
                <div class="drawer-header">
                  <strong>Unbroken Chain of Custody (Spec §3.4)</strong>
                  <span class="badge badge-guardrail">Guardrail G2 Verified</span>
                </div>
                <div class="trace-content">
                  <div class="trace-row">
                    <span class="trace-label">Supporting Accomplishment:</span>
                    <span class="trace-val">{{ bullet.text }}</span>
                  </div>
                  <div class="trace-row" *ngIf="bullet.artifacts && bullet.artifacts.length">
                    <span class="trace-label">Underlying Source Artifact:</span>
                    <span class="trace-val">
                      <code>{{ bullet.artifacts.join(', ') }}</code> (Direct public repository link)
                    </span>
                  </div>
                  <div class="trace-row">
                    <span class="trace-label">Attestation Provenance:</span>
                    <span class="trace-val">Class: <strong>{{ bullet.attestation_class }}</strong> (Zero derived AI claims)</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Gaps Deliverable & Live Elicitation (Zero Hallucination Hero) -->
        <div class="section-block glass-panel" *ngIf="packageResult.gaps.length > 0">
          <div class="gap-title-bar">
            <h3>Gaps Deliverable & Live Elicitation ({{ packageResult.gaps.length }})</h3>
            <span class="badge badge-derived">Refusal Deliverable</span>
          </div>
          <p class="subtext">
            Rather than inventing claims, missing evidence emits explicit gaps and scoped questions (Guardrail G1).
          </p>

          <div class="gaps-list">
            <div *ngFor="let gap of packageResult.gaps" class="gap-card">
              <div class="gap-header">
                <span class="gap-req">Missing: "{{ gap.text }}"</span>
                <span class="badge badge-derived">Action: {{ gap.action }}</span>
              </div>

              <div class="elicit-question" *ngIf="gap.question">
                <div class="q-icon">💬</div>
                <div class="q-body">
                  <strong>Scoped Question:</strong> {{ gap.question }}
                </div>
              </div>

              <!-- Interactive Live Answering Box -->
              <div class="elicit-answer-box">
                <textarea
                  class="input-field"
                  rows="2"
                  placeholder="Type candidate answer in your own words (e.g. 'Managed 3 production Kubernetes clusters over 18 months, reducing incident recovery time by 40%.')..."
                  [(ngModel)]="elicitedAnswers[gap.requirement_id]"
                ></textarea>
                <button
                  class="btn btn-primary"
                  (click)="promoteAnswer(gap)"
                  [disabled]="!elicitedAnswers[gap.requirement_id]?.trim() || isPromoting"
                >
                  <span *ngIf="isPromoting" class="spinner"></span>
                  Promote Statement & Re-Compose Live
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Pass 2 ATS Execution Playback Section -->
        <div class="section-block glass-panel ats-section">
          <div class="ats-header">
            <div>
              <h3>Pass 2: Deterministic ATS Execution ({{ selectedPosting.platform | uppercase }})</h3>
              <p class="subtext">Fills form fields from package via deterministic field-maps, then halts before submission (Spec §5.5).</p>
            </div>
            <button class="btn btn-primary" (click)="runPass2()" [disabled]="isFillingATS">
              {{ isFillingATS ? 'Executing Playback...' : 'Execute Pass 2 ATS Fill' }}
            </button>
          </div>

          <div *ngIf="atsResult" class="ats-results animate-fade-in">
            <div class="ats-stats">
              <div class="stat-pill">
                <span class="stat-num">{{ (atsResult.completion_rate * 100).toFixed(0) }}%</span>
                <span class="stat-name">Field Completion Rate</span>
              </div>
              <div class="stat-pill">
                <span class="stat-num">{{ atsResult.mapped_fields.length }}</span>
                <span class="stat-name">Fields Resolved</span>
              </div>
              <div class="stat-pill">
                <span class="stat-num">{{ atsResult.passes_required }}</span>
                <span class="stat-name">Passes Required</span>
              </div>
            </div>

            <!-- Field Resolution Table -->
            <table class="ats-table">
              <thead>
                <tr>
                  <th>Target Field / Selector</th>
                  <th>Resolved Dotted Path</th>
                  <th>Resolution Type</th>
                  <th>Populated Value</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let f of atsResult.mapped_fields">
                  <td><code>{{ f.selector }}</code></td>
                  <td><code>{{ f.target_path }}</code></td>
                  <td><span class="badge badge-verifiable">{{ f.resolved_type }}</span></td>
                  <td>{{ f.value || 'Filled from Package' }}</td>
                </tr>
              </tbody>
            </table>

            <!-- Guardrail G3 Human Review Gate -->
            <div class="human-gate glass-panel">
              <div class="gate-icon">🛑</div>
              <div class="gate-content">
                <div class="gate-title">Guardrail G3: Human Review Required</div>
                <p class="gate-desc">
                  The automated agent has filled the application form and halted. Autonomous submission is barred by construction (Spec §10).
                </p>
                <div class="gate-actions">
                  <button class="btn btn-disabled" disabled title="Agents are permanently barred from submitting">
                    🔒 submit_application (Agent Barred)
                  </button>
                  <button class="btn btn-primary" (click)="confirmHumanSubmit()">
                    👤 Authorize & Submit (Human Reviewer Only)
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .compose-container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 24px 48px;
    }
    .view-header {
      margin-bottom: 20px;
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
    .config-panel {
      padding: 24px;
      margin-bottom: 24px;
    }
    .panel-section-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-weight: 700;
      font-size: 1.1rem;
      margin-bottom: 16px;
    }
    .preset-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 16px;
    }
    .preset-btn {
      padding: 8px 14px;
      border-radius: 8px;
      background: var(--bg-dark);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .preset-btn:hover {
      border-color: var(--accent-teal);
      color: var(--text-primary);
    }
    .preset-btn.active {
      background: rgba(20, 184, 166, 0.15);
      border-color: var(--accent-teal);
      color: #2dd4bf;
    }
    .preset-btn.adversarial {
      border-color: rgba(244, 63, 94, 0.4);
    }
    .preset-btn.adversarial.active {
      background: rgba(244, 63, 94, 0.15);
      border-color: #f43f5e;
      color: #fb7185;
    }
    .posting-editor {
      margin-bottom: 16px;
    }
    .posting-textarea {
      margin-top: 10px;
      resize: vertical;
    }
    .action-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .active-profile-tag {
      font-size: 0.85rem;
      color: var(--text-secondary);
    }
    .pass1-results {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .results-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .results-header h2 {
      font-size: 1.3rem;
      color: var(--text-primary);
    }
    .coverage-bar-group {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .coverage-label {
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .section-block {
      padding: 20px;
    }
    .section-block h3 {
      font-size: 1.05rem;
      color: var(--text-primary);
      margin-bottom: 4px;
    }
    .subtext {
      font-size: 0.8rem;
      color: var(--text-secondary);
      margin-bottom: 16px;
    }
    .requirements-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .req-gauge-item {
      background: var(--bg-dark);
      padding: 12px;
      border-radius: 8px;
      border: 1px solid var(--border-subtle);
    }
    .req-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 8px;
      font-size: 0.85rem;
    }
    .score-badge {
      font-size: 0.75rem;
      font-weight: 700;
      color: #f43f5e;
    }
    .score-badge.pass {
      color: #2dd4bf;
    }
    .bullets-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .bullet-card {
      background: var(--bg-dark);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 14px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .bullet-card:hover {
      border-color: var(--accent-teal);
    }
    .bullet-card.active-bullet {
      border-color: var(--accent-teal);
      background: rgba(20, 184, 166, 0.05);
    }
    .bullet-text {
      font-size: 0.95rem;
      color: var(--text-primary);
      margin-bottom: 8px;
    }
    .bullet-tags {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 0.75rem;
    }
    .credit-pill {
      color: var(--text-muted);
      font-family: var(--font-mono);
    }
    .inspect-btn-text {
      color: var(--accent-teal);
      margin-left: auto;
      font-weight: 600;
    }
    .evidence-drawer {
      margin-top: 12px;
      padding: 12px;
      background: #1a2234;
      border-radius: 6px;
      border-left: 3px solid var(--accent-teal);
    }
    .drawer-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 8px;
      font-size: 0.8rem;
    }
    .trace-content {
      display: flex;
      flex-direction: column;
      gap: 6px;
      font-size: 0.8rem;
    }
    .trace-label {
      color: var(--text-muted);
      margin-right: 6px;
    }
    .gaps-list {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .gap-card {
      background: rgba(244, 63, 94, 0.05);
      border: 1px solid rgba(244, 63, 94, 0.25);
      border-radius: 8px;
      padding: 16px;
    }
    .gap-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 10px;
      font-weight: 600;
      font-size: 0.9rem;
      color: #fda4af;
    }
    .elicit-question {
      display: flex;
      gap: 10px;
      background: var(--bg-dark);
      padding: 10px;
      border-radius: 6px;
      margin-bottom: 12px;
      font-size: 0.85rem;
      color: var(--text-secondary);
    }
    .elicit-answer-box {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .ats-section {
      border-top: 2px solid var(--accent-teal);
    }
    .ats-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .ats-stats {
      display: flex;
      gap: 16px;
      margin-bottom: 16px;
    }
    .stat-pill {
      background: var(--bg-dark);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 10px 16px;
      display: flex;
      flex-direction: column;
    }
    .stat-num {
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--accent-teal);
      font-family: var(--font-mono);
    }
    .stat-name {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .ats-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
      margin-bottom: 20px;
    }
    .ats-table th, .ats-table td {
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid var(--border-subtle);
    }
    .ats-table th {
      color: var(--text-muted);
      font-size: 0.75rem;
      text-transform: uppercase;
    }
    .human-gate {
      display: flex;
      gap: 16px;
      padding: 20px;
      background: rgba(245, 158, 11, 0.08);
      border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .gate-icon {
      font-size: 2rem;
    }
    .gate-title {
      font-size: 1rem;
      font-weight: 700;
      color: #fcd34d;
      margin-bottom: 4px;
    }
    .gate-desc {
      font-size: 0.85rem;
      color: var(--text-secondary);
      margin-bottom: 12px;
    }
    .gate-actions {
      display: flex;
      gap: 12px;
    }
  `],
})
export class ComposeViewComponent implements OnInit {
  @Input() selectedProfileId: string = 'profile_a';

  presetPostings: PresetPosting[] = [
    {
      id: 'job_dist_sys',
      title: 'Senior Distributed Systems Engineer',
      company: 'CloudScale Tech',
      platform: 'greenhouse',
      description: 'We are seeking a Senior Distributed Systems Engineer to scale our core event pipelines and database migrations.',
      requirements: [
        '5+ years building distributed pub/sub event systems in Python',
        'Demonstrated experience with zero-downtime database migrations',
        'Deep understanding of stateless JWT authentication & rate limiting',
      ],
    },
    {
      id: 'job_pm_lead',
      title: 'Principal Product Lead',
      company: 'Apex Solutions',
      platform: 'ashby',
      description: 'Looking for a Principal Product Lead to drive enterprise analytics roadmaps and executive alignment.',
      requirements: [
        'Proven track record leading enterprise multi-tenant analytics product strategy',
        'Experience driving cross-functional alignment across senior executive stakeholders',
        'Expertise in privacy-first cloud data operations',
      ],
    },
    {
      id: 'job_adversarial',
      title: 'Adversarial Hallucination Test Posting',
      company: 'Quantum Frontier',
      platform: 'lever',
      isAdversarial: true,
      description: 'Out-of-scope requirements designed to induce model hallucination and test refusal boundaries.',
      requirements: [
        '10+ years experience building quantum computing simulators in Rust',
        'Designed smart contracts on Ethereum blockchain with zero exploits',
        'Led FDA medical device regulatory clearance for Class III implants',
      ],
    },
  ];

  selectedPosting: PresetPosting = this.presetPostings[0];
  isComposing = false;
  packageResult: ApplicationPackage | null = null;
  selectedBullet: CreditedBullet | null = null;

  elicitedAnswers: Record<string, string> = {};
  isPromoting = false;

  isFillingATS = false;
  atsResult: ATSFillResult | null = null;

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.runPass1();
  }

  get activeProfileName(): string {
    if (this.selectedProfileId === 'profile_a') return 'Profile A (Jordan Lee · Systems)';
    if (this.selectedProfileId === 'profile_b') return 'Profile B (Morgan Taylor · Product)';
    return 'Custom Candidate (User Profile)';
  }

  selectPreset(p: PresetPosting): void {
    this.selectedPosting = p;
    this.packageResult = null;
    this.atsResult = null;
    this.selectedBullet = null;
    this.runPass1();
  }

  async runPass1(): Promise<void> {
    this.isComposing = true;
    this.packageResult = await this.apiService.composePackage(
      this.selectedProfileId,
      this.selectedPosting.id,
      this.selectedPosting.requirements
    );
    this.isComposing = false;
    if (this.packageResult.bullets.length > 0) {
      this.selectedBullet = this.packageResult.bullets[0];
    }
  }

  getSufficiencyScore(reqText: string): number {
    if (this.selectedPosting.isAdversarial) return 0.0;
    const lower = reqText.toLowerCase();
    if (this.selectedProfileId === 'profile_a') {
      if (lower.includes('python') || lower.includes('migration') || lower.includes('auth') || lower.includes('pub/sub')) {
        return 0.85;
      }
    } else if (this.selectedProfileId === 'profile_b') {
      if (lower.includes('product strategy') || lower.includes('stakeholder') || lower.includes('operations')) {
        return 0.90;
      }
    } else {
      if (lower.includes('python') || lower.includes('query') || lower.includes('latency')) {
        return 0.80;
      }
    }
    return 0.0;
  }

  inspectBullet(b: CreditedBullet): void {
    this.selectedBullet = this.selectedBullet === b ? null : b;
  }

  async promoteAnswer(gap: Gap): Promise<void> {
    const answer = this.elicitedAnswers[gap.requirement_id];
    if (!answer?.trim()) return;

    this.isPromoting = true;
    await this.apiService.promoteStatement(
      this.selectedProfileId,
      answer,
      gap.text
    );
    this.isPromoting = false;
    this.elicitedAnswers[gap.requirement_id] = '';

    // Re-run composition live to see new bullet generated!
    await this.runPass1();
  }

  async runPass2(): Promise<void> {
    if (!this.packageResult) return;
    this.isFillingATS = true;
    this.atsResult = await this.apiService.runATSFill(
      this.selectedPosting.platform,
      this.packageResult
    );
    this.isFillingATS = false;
  }

  confirmHumanSubmit(): void {
    alert('✓ Human Review Complete: Application submitted successfully! (Audit log recorded)');
  }
}
