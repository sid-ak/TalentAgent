import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
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
            Manage ground-truth candidate experience across modalities: Resume PDFs, GitHub repositories, and verbatim user statements.
          </p>
        </div>
      </div>

      <!-- Profile Selector Cards -->
      <div class="profile-grid">
        <div
          *ngFor="let prof of profiles"
          class="profile-card glass-panel"
          [class.selected]="selectedProfileId === prof.id"
          (click)="selectProfile(prof.id)"
        >
          <div class="card-header">
            <div>
              <div class="profile-name">{{ prof.name }}</div>
              <div class="profile-type">{{ prof.type }}</div>
            </div>
            <div class="badge" [ngClass]="getProfileBadgeClass(prof.id)">
              {{ prof.node_count }} nodes
            </div>
          </div>
          <p class="profile-desc">{{ prof.description }}</p>
          <div class="profile-footer">
            <span class="location-tag">📍 {{ prof.identity.location || 'Remote' }}</span>
            <span class="select-hint">{{ selectedProfileId === prof.id ? '✓ Active Profile' : 'Select Profile →' }}</span>
          </div>
        </div>
      </div>

      <!-- Custom Profile Management Section (Only visible for Custom Profile) -->
      <div *ngIf="selectedProfileId === 'custom'" class="custom-studio glass-panel">
        <div class="studio-header">
          <h2>Custom Candidate Studio</h2>
          <span class="badge badge-verifiable">User-Originated Knowledge Layer</span>
        </div>

        <div class="studio-grid">
          <!-- Left Column: Resume PDF Upload & Contact Details -->
          <div class="studio-col">
            <div class="section-card">
              <h3>📄 Ingest Resume (PDF / Text)</h3>
              <p class="subtext">Extract candidate experience and work history directly into evidence nodes via <code>pypdf</code>.</p>
              
              <div class="drop-zone" (click)="fileInput.click()">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                <div class="drop-label">
                  <strong>Click to upload Resume PDF</strong> or drag & drop
                </div>
                <div class="drop-note">{{ uploadedResumeName || 'Supports .pdf, .txt' }}</div>
                <input
                  #fileInput
                  type="file"
                  accept=".pdf,.txt"
                  style="display: none"
                  (change)="onFileSelected($event)"
                />
              </div>

              <div *ngIf="isUploading" class="uploading-state">
                <span class="spinner"></span> Parsing PDF with pypdf and extracting candidate nodes...
              </div>

              <div *ngIf="uploadSuccessMsg" class="alert-success">
                ✓ {{ uploadSuccessMsg }}
              </div>
            </div>

            <!-- GitHub Repo Sync -->
            <div class="section-card">
              <h3>🐙 Sync GitHub Repositories</h3>
              <p class="subtext">Ingest public pull requests, commits, and RFC design documents into verifiable artifacts.</p>

              <div class="form-row">
                <input
                  type="text"
                  class="input-field"
                  placeholder="GitHub Username (e.g. alexrivers)"
                  [(ngModel)]="githubUser"
                />
                <input
                  type="text"
                  class="input-field"
                  placeholder="Repository (e.g. query-engine)"
                  [(ngModel)]="githubRepo"
                />
              </div>

              <button class="btn btn-primary" (click)="syncGithub()" [disabled]="!githubUser || !githubRepo">
                Sync Repository Artifacts
              </button>
            </div>
          </div>

          <!-- Right Column: Raw Verbatim Statement Input -->
          <div class="studio-col">
            <div class="section-card">
              <h3>✍️ Direct Accomplishment Statements</h3>
              <p class="subtext">
                Record claims directly in candidate's own words (Invariant 3). Saved verbatim with byte-for-byte retention and marked <code>attested</code>.
              </p>

              <textarea
                class="input-field textarea-field"
                rows="4"
                placeholder="e.g. Architected streaming buffer pools reducing p99 database query latency by 45% across 200M rows."
                [(ngModel)]="rawStatementText"
              ></textarea>

              <div class="statement-actions">
                <input
                  type="text"
                  class="input-field skill-input"
                  placeholder="Key Skills (comma-separated, e.g. Python, SQL)"
                  [(ngModel)]="statementSkills"
                />
                <button
                  class="btn btn-primary"
                  (click)="addStatement()"
                  [disabled]="!rawStatementText.trim()"
                >
                  Save Verbatim Statement
                </button>
              </div>

              <div *ngIf="statementSuccessMsg" class="alert-success">
                ✓ {{ statementSuccessMsg }}
              </div>
            </div>

            <!-- Candidate Identity Form -->
            <div class="section-card">
              <h3>👤 Identity & Materials</h3>
              <div class="form-row">
                <input type="text" class="input-field" placeholder="First Name" [(ngModel)]="customProfile.identity.first_name" />
                <input type="text" class="input-field" placeholder="Last Name" [(ngModel)]="customProfile.identity.last_name" />
              </div>
              <div class="form-row">
                <input type="email" class="input-field" placeholder="Email" [(ngModel)]="customProfile.identity.email" />
                <input type="text" class="input-field" placeholder="Location" [(ngModel)]="customProfile.identity.location" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Current Profile Evidence Nodes Overview -->
      <div class="nodes-overview glass-panel">
        <div class="overview-header">
          <h3>Ground-Truth Evidence Nodes ({{ currentNodes.length }})</h3>
          <div class="legend">
            <span class="badge badge-verifiable">Verifiable (Public PRs/Docs)</span>
            <span class="badge badge-attested">Attested (Statements)</span>
          </div>
        </div>

        <div class="nodes-list">
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
                  <a [href]="node.url" target="_blank">🔗 Inspect Source Artifact</a>
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
      margin-bottom: 24px;
    }
    .view-title {
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 6px;
    }
    .view-desc {
      color: var(--text-secondary);
      font-size: 0.95rem;
    }
    .profile-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .profile-card {
      padding: 20px;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .profile-card:hover {
      border-color: var(--accent-teal);
      transform: translateY(-2px);
    }
    .profile-card.selected {
      border-color: var(--accent-teal);
      background: rgba(20, 184, 166, 0.08);
      box-shadow: 0 0 0 1px var(--accent-teal);
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 10px;
    }
    .profile-name {
      font-weight: 700;
      font-size: 1.05rem;
      color: var(--text-primary);
    }
    .profile-type {
      font-size: 0.75rem;
      color: var(--accent-teal);
      margin-top: 2px;
    }
    .profile-desc {
      font-size: 0.85rem;
      color: var(--text-secondary);
      line-height: 1.4;
      margin-bottom: 16px;
    }
    .profile-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.75rem;
      color: var(--text-muted);
      border-top: 1px solid var(--border-subtle);
      padding-top: 10px;
    }
    .select-hint {
      color: var(--accent-teal);
      font-weight: 600;
    }
    .custom-studio {
      padding: 24px;
      margin-bottom: 24px;
    }
    .studio-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border-subtle);
    }
    .studio-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    @media (max-width: 840px) {
      .studio-grid { grid-template-columns: 1fr; }
    }
    .section-card {
      background: var(--bg-dark);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 16px;
    }
    .section-card h3 {
      font-size: 0.95rem;
      color: var(--text-primary);
      margin-bottom: 4px;
    }
    .subtext {
      font-size: 0.75rem;
      color: var(--text-secondary);
      margin-bottom: 12px;
    }
    .drop-zone {
      border: 2px dashed var(--border-highlight);
      border-radius: 8px;
      padding: 24px;
      text-align: center;
      cursor: pointer;
      color: var(--text-secondary);
      transition: all 0.15s ease;
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
    .form-row {
      display: flex;
      gap: 10px;
      margin-bottom: 10px;
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
      margin-top: 10px;
      padding: 8px 12px;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #34d399;
      border-radius: 6px;
      font-size: 0.8rem;
    }
    .uploading-state {
      margin-top: 10px;
      font-size: 0.8rem;
      color: var(--accent-amber);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .nodes-overview {
      padding: 20px;
    }
    .overview-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .nodes-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .node-item {
      display: flex;
      gap: 14px;
      padding: 12px;
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
  @Input() selectedProfileId: string = 'profile_a';
  @Output() profileSelected = new EventEmitter<string>();

  profiles: CandidateProfile[] = [];
  currentNodes: EvidenceNode[] = [];
  
  // Custom Profile state
  customProfile: CandidateProfile = {
    id: 'custom',
    name: 'Custom Candidate',
    type: 'User Profile',
    description: '',
    node_count: 0,
    attestation_classes: [],
    identity: { first_name: 'Alex', last_name: 'Rivers', email: 'alex.rivers@example.com', location: 'San Francisco, CA' },
  };

  uploadedResumeName = '';
  isUploading = false;
  uploadSuccessMsg = '';

  githubUser = 'alexrivers';
  githubRepo = 'query-engine';

  rawStatementText = '';
  statementSkills = 'Python, Distributed Systems';
  statementSuccessMsg = '';

  constructor(private apiService: ApiService) {}

  async ngOnInit(): Promise<void> {
    await this.loadProfiles();
    await this.loadCurrentNodes();
  }

  async loadProfiles(): Promise<void> {
    this.profiles = await this.apiService.getProfiles();
    const custom = this.profiles.find(p => p.id === 'custom');
    if (custom) {
      this.customProfile = custom;
    }
  }

  async selectProfile(profileId: string): Promise<void> {
    this.selectedProfileId = profileId;
    this.profileSelected.emit(profileId);
    await this.loadCurrentNodes();
  }

  async loadCurrentNodes(): Promise<void> {
    const graphData = await this.apiService.getEvidenceGraph(this.selectedProfileId);
    this.currentNodes = graphData.nodes || [];
  }

  getProfileBadgeClass(profileId: string): string {
    if (profileId === 'profile_a') return 'badge-verifiable';
    if (profileId === 'profile_b') return 'badge-attested';
    return 'badge-corroborated';
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
      this.uploadSuccessMsg = `Resume extracted successfully (${res.nodes_added || 4} candidate accomplishments created).`;
      await this.loadCurrentNodes();
      await this.loadProfiles();
    };
    reader.readAsDataURL(file);
  }

  async syncGithub(): Promise<void> {
    if (!this.githubUser || !this.githubRepo) return;
    const res = await this.apiService.syncGithub(this.githubUser, this.githubRepo);
    this.uploadSuccessMsg = `GitHub repo ${this.githubUser}/${this.githubRepo} synced (${res.attestation_class} artifact created).`;
    await this.loadCurrentNodes();
    await this.loadProfiles();
  }

  async addStatement(): Promise<void> {
    if (!this.rawStatementText.trim()) return;
    const skills = this.statementSkills.split(',').map(s => s.trim()).filter(Boolean);
    const res = await this.apiService.addStatement(this.rawStatementText, skills);
    this.statementSuccessMsg = `Statement saved byte-for-byte to graph (ID: ${res.statement_id}, class: ${res.attestation_class}).`;
    this.rawStatementText = '';
    await this.loadCurrentNodes();
    await this.loadProfiles();
  }
}
