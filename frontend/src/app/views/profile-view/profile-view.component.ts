import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { CandidateProfile, EvidenceNode } from '../../models/talentagent.models';

@Component({
  selector: 'app-profile-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="profile-container animate-fade-in">
      <div class="view-header">
        <div>
          <h1 class="view-title">Candidate Profile Studio</h1>
          <p class="view-desc">
            Build and manage your verifiable career evidence. Ingest your resume PDF, connect code repositories, and record accomplishments in your own words.
          </p>
        </div>
        <div class="header-actions">
          <button class="btn btn-secondary" (click)="resetProfile()">
            Reset Profile Data
          </button>
        </div>
      </div>

      <div class="studio-grid">
        <!-- Left Column: Identity & Resume Upload -->
        <div class="studio-col">
          <!-- Candidate Identity Form -->
          <div class="section-card glass-panel">
            <div class="card-title-row">
              <h3>👤 Personal & Contact Details</h3>
              <span class="badge badge-verifiable">Candidate Record</span>
            </div>
            <p class="subtext">Used to populate ATS contact fields and generate candidate packages.</p>

            <div class="form-row">
              <input
                type="text"
                class="input-field"
                placeholder="First Name"
                [(ngModel)]="profile.identity.first_name"
                (change)="saveIdentity()"
              />
              <input
                type="text"
                class="input-field"
                placeholder="Last Name"
                [(ngModel)]="profile.identity.last_name"
                (change)="saveIdentity()"
              />
            </div>

            <div class="form-row">
              <input
                type="email"
                class="input-field"
                placeholder="Email Address"
                [(ngModel)]="profile.identity.email"
                (change)="saveIdentity()"
              />
              <input
                type="tel"
                class="input-field"
                placeholder="Phone Number"
                [(ngModel)]="profile.identity.phone"
                (change)="saveIdentity()"
              />
            </div>

            <div class="form-row">
              <input
                type="text"
                class="input-field"
                placeholder="Location (e.g. San Francisco, CA)"
                [(ngModel)]="profile.identity.location"
                (change)="saveIdentity()"
              />
            </div>

            <div class="card-divider"></div>

            <div class="card-title-row">
              <h3>🔗 Links & Profiles</h3>
            </div>

            <div class="form-row">
              <input
                type="url"
                class="input-field"
                placeholder="LinkedIn Profile URL"
                [(ngModel)]="profile.links.linkedin"
                (change)="saveIdentity()"
              />
            </div>
            <div class="form-row">
              <input
                type="url"
                class="input-field"
                placeholder="GitHub Profile URL"
                [(ngModel)]="profile.links.github"
                (change)="saveIdentity()"
              />
              <input
                type="url"
                class="input-field"
                placeholder="Portfolio / Personal Website"
                [(ngModel)]="profile.links.portfolio"
                (change)="saveIdentity()"
              />
            </div>
          </div>

          <!-- Resume Ingestion -->
          <div class="section-card glass-panel">
            <div class="card-title-row">
              <h3>📄 Ingest Resume (PDF or Text)</h3>
              <span class="badge badge-verifiable">Automated Parser</span>
            </div>
            <p class="subtext">
              Extract work claims, project achievements, and skills directly into your evidence graph using <code>pypdf</code>.
            </p>

            <div class="drop-zone" (click)="fileInput.click()">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              <div class="drop-label">
                <strong>Click to upload Resume PDF</strong> or drag & drop file
              </div>
              <div class="drop-note">{{ uploadedResumeName || profile.resume_filename || 'Supports .pdf, .txt' }}</div>
              <input
                #fileInput
                type="file"
                accept=".pdf,.txt"
                style="display: none"
                (change)="onFileSelected($event)"
              />
            </div>

            <div *ngIf="isUploading" class="uploading-state">
              <span class="spinner"></span> Parsing PDF with pypdf and extracting accomplishment nodes...
            </div>

            <div *ngIf="uploadSuccessMsg" class="alert-success">
              ✓ {{ uploadSuccessMsg }}
            </div>
          </div>
        </div>

        <!-- Right Column: GitHub Sync & Direct Accomplishment Statements -->
        <div class="studio-col">
          <!-- GitHub Sync -->
          <div class="section-card glass-panel">
            <div class="card-title-row">
              <h3>🐙 Ingest GitHub Repositories</h3>
              <span class="badge badge-verifiable">Verifiable Artifacts</span>
            </div>
            <p class="subtext">
              Index public pull requests, commits, and architecture documentation as verifiable ground-truth evidence.
            </p>

            <div class="form-row">
              <input
                type="text"
                class="input-field"
                placeholder="GitHub Username"
                [(ngModel)]="githubUser"
              />
              <input
                type="text"
                class="input-field"
                placeholder="Repository Name"
                [(ngModel)]="githubRepo"
              />
            </div>

            <button
              class="btn btn-primary"
              (click)="syncGithub()"
              [disabled]="!githubUser || !githubRepo || isSyncingRepo"
            >
              <span *ngIf="isSyncingRepo" class="spinner"></span>
              {{ isSyncingRepo ? 'Syncing...' : 'Sync Repository Evidence' }}
            </button>

            <div *ngIf="githubSuccessMsg" class="alert-success">
              ✓ {{ githubSuccessMsg }}
            </div>
          </div>

          <!-- Direct Accomplishment Statements -->
          <div class="section-card glass-panel">
            <div class="card-title-row">
              <h3>✍️ Direct Accomplishment Statements</h3>
              <span class="badge badge-attested">Attested Entry</span>
            </div>
            <p class="subtext">
              Record career achievements in your own words (Invariant 3). Saved verbatim with byte-for-byte retention and marked <code>attested</code>.
            </p>

            <textarea
              class="input-field textarea-field"
              rows="4"
              placeholder="e.g. Designed and scaled streaming pub/sub pipeline in Python handling 50k events/sec with zero message drop."
              [(ngModel)]="rawStatementText"
            ></textarea>

            <div class="statement-actions">
              <input
                type="text"
                class="input-field skill-input"
                placeholder="Key Skills (comma-separated, e.g. Python, Distributed Systems)"
                [(ngModel)]="statementSkills"
              />
              <button
                class="btn btn-primary"
                (click)="addStatement()"
                [disabled]="!rawStatementText.trim() || isAddingStatement"
              >
                <span *ngIf="isAddingStatement" class="spinner"></span>
                Save Statement
              </button>
            </div>

            <div *ngIf="statementSuccessMsg" class="alert-success">
              ✓ {{ statementSuccessMsg }}
            </div>
          </div>
        </div>
      </div>

      <!-- Current Evidence Graph Overview -->
      <div class="nodes-overview glass-panel">
        <div class="overview-header">
          <h3>Your Active Evidence Nodes ({{ currentNodes.length }})</h3>
          <div class="legend">
            <span class="badge badge-verifiable">Verifiable (Code / Docs)</span>
            <span class="badge badge-attested">Attested (Statements)</span>
          </div>
        </div>

        <div *ngIf="currentNodes.length === 0" class="empty-nodes">
          <div class="empty-icon">📭</div>
          <div class="empty-title">No evidence nodes recorded yet</div>
          <p class="empty-sub">
            Upload your resume PDF above or enter accomplishment statements to start building your verifiable career graph.
          </p>
        </div>

        <div *ngIf="currentNodes.length > 0" class="nodes-list">
          <div *ngFor="let node of currentNodes" class="node-item">
            <div class="node-badge-col">
              <span
                class="badge"
                [class.badge-verifiable]="node.attestation_class === 'verifiable' || node.type === 'artifact'"
                [class.badge-attested]="node.attestation_class === 'attested' || node.type === 'statement'"
                [class.badge-derived]="node.attestation_class === 'derived'"
              >
                {{ node.attestation_class || node.type }}
              </span>
            </div>
            <div class="node-content-col">
              <div class="node-title">
                {{ node.claim || node.title || node.raw || node.name }}
              </div>
              <div class="node-meta">
                <span class="node-id">ID: {{ node.id }}</span>
                <span *ngIf="node.skills?.length" class="skills-tag">
                  Skills: {{ node.skills?.join(', ') }}
                </span>
                <span *ngIf="node.url" class="source-link">
                  <a [href]="node.url" target="_blank">🔗 View Artifact</a>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .profile-container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 24px 48px;
    }
    .view-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 24px;
      gap: 16px;
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
    .studio-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      margin-bottom: 24px;
    }
    @media (max-width: 860px) {
      .studio-grid { grid-template-columns: 1fr; }
    }
    .section-card {
      padding: 20px;
      margin-bottom: 20px;
    }
    .card-title-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;
    }
    .card-title-row h3 {
      font-size: 1rem;
      color: var(--text-primary);
    }
    .subtext {
      font-size: 0.8rem;
      color: var(--text-secondary);
      margin-bottom: 16px;
    }
    .card-divider {
      height: 1px;
      background: var(--border-subtle);
      margin: 16px 0;
    }
    .form-row {
      display: flex;
      gap: 10px;
      margin-bottom: 12px;
    }
    .drop-zone {
      border: 2px dashed var(--border-highlight);
      border-radius: 8px;
      padding: 28px;
      text-align: center;
      cursor: pointer;
      color: var(--text-secondary);
      transition: all 0.15s ease;
      background: var(--bg-dark);
    }
    .drop-zone:hover {
      border-color: var(--accent-teal);
      color: var(--accent-teal);
      background: rgba(20, 184, 166, 0.05);
    }
    .drop-label {
      margin-top: 8px;
      font-size: 0.875rem;
    }
    .drop-note {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 2px;
    }
    .textarea-field {
      resize: vertical;
      margin-bottom: 10px;
    }
    .statement-actions {
      display: flex;
      gap: 10px;
    }
    .alert-success {
      margin-top: 12px;
      padding: 10px 14px;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #34d399;
      border-radius: 6px;
      font-size: 0.825rem;
    }
    .uploading-state {
      margin-top: 12px;
      font-size: 0.825rem;
      color: var(--accent-amber);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .nodes-overview {
      padding: 24px;
    }
    .overview-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .empty-nodes {
      text-align: center;
      padding: 40px 20px;
      color: var(--text-muted);
    }
    .empty-icon {
      font-size: 2.5rem;
      margin-bottom: 8px;
    }
    .empty-title {
      font-size: 1rem;
      font-weight: 600;
      color: var(--text-secondary);
      margin-bottom: 4px;
    }
    .empty-sub {
      font-size: 0.85rem;
    }
    .nodes-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .node-item {
      display: flex;
      gap: 14px;
      padding: 12px 16px;
      background: var(--bg-dark);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      align-items: flex-start;
    }
    .node-title {
      font-size: 0.875rem;
      color: var(--text-primary);
      margin-bottom: 4px;
      font-weight: 500;
    }
    .node-meta {
      display: flex;
      gap: 12px;
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .source-link a {
      color: var(--accent-teal);
      text-decoration: none;
    }
    .source-link a:hover {
      text-decoration: underline;
    }
  `],
})
export class ProfileViewComponent implements OnInit {
  profile: CandidateProfile = {
    identity: { first_name: '', last_name: '', email: '', phone: '', location: '' },
    links: { github: '', linkedin: '', portfolio: '' },
    resume_filename: null,
    node_count: 0,
    has_profile: false,
  };

  currentNodes: EvidenceNode[] = [];

  uploadedResumeName = '';
  isUploading = false;
  uploadSuccessMsg = '';

  githubUser = '';
  githubRepo = '';
  isSyncingRepo = false;
  githubSuccessMsg = '';

  rawStatementText = '';
  statementSkills = '';
  isAddingStatement = false;
  statementSuccessMsg = '';

  constructor(private apiService: ApiService) {}

  async ngOnInit(): Promise<void> {
    await this.loadProfile();
    await this.loadNodes();
  }

  async loadProfile(): Promise<void> {
    this.profile = await this.apiService.getProfile();
  }

  async loadNodes(): Promise<void> {
    const graphData = await this.apiService.getEvidenceGraph();
    this.currentNodes = graphData.nodes || [];
  }

  async saveIdentity(): Promise<void> {
    this.profile = await this.apiService.updateProfile(this.profile.identity, this.profile.links);
  }

  async onFileSelected(event: Event): Promise<void> {
    const target = event.target as HTMLInputElement;
    if (!target.files || target.files.length === 0) return;

    const file = target.files[0];
    this.uploadedResumeName = file.name;
    this.isUploading = true;
    this.uploadSuccessMsg = '';

    const reader = new FileReader();
    reader.onload = async () => {
      const base64Content = (reader.result as string).split(',')[1];
      const res = await this.apiService.uploadResume(base64Content, undefined, file.name);
      this.isUploading = false;
      this.uploadSuccessMsg = `Resume extracted successfully (${res.nodes_added || 0} accomplishment nodes added).`;
      await this.loadNodes();
      await this.loadProfile();
    };
    reader.readAsDataURL(file);
  }

  async syncGithub(): Promise<void> {
    if (!this.githubUser || !this.githubRepo) return;
    this.isSyncingRepo = true;
    this.githubSuccessMsg = '';
    const res = await this.apiService.syncGithub(this.githubUser, this.githubRepo);
    this.isSyncingRepo = false;
    this.githubSuccessMsg = `Repository ${this.githubUser}/${this.githubRepo} synced (${res.attestation_class} artifact indexed).`;
    await this.loadNodes();
    await this.loadProfile();
  }

  async addStatement(): Promise<void> {
    if (!this.rawStatementText.trim()) return;
    this.isAddingStatement = true;
    this.statementSuccessMsg = '';
    const skills = this.statementSkills.split(',').map((s) => s.trim()).filter(Boolean);
    const res = await this.apiService.addStatement(this.rawStatementText, skills);
    this.isAddingStatement = false;
    this.statementSuccessMsg = `Statement saved byte-for-byte (ID: ${res.statement_id}, class: ${res.attestation_class}).`;
    this.rawStatementText = '';
    this.statementSkills = '';
    await this.loadNodes();
    await this.loadProfile();
  }

  async resetProfile(): Promise<void> {
    if (!confirm('Are you sure you want to reset your candidate profile and clear the evidence store?')) {
      return;
    }
    await this.apiService.resetProfile();
    await this.loadProfile();
    await this.loadNodes();
  }
}
