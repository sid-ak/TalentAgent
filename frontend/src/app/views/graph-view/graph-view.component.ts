import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api.service';
import { EvidenceEdge, EvidenceNode, GraphData } from '../../models/talentagent.models';

@Component({
  selector: 'app-graph-view',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="graph-container animate-fade-in">
      <div class="view-header">
        <div>
          <h1 class="view-title">Evidence Graph & Quarantine Explorer</h1>
          <p class="view-desc">
            Visualizes candidate accomplishments, inspectable source artifacts, user statements, and the <strong>Derived Quarantine Boundary</strong> (Guardrail G1).
          </p>
        </div>

        <div class="filter-group" *ngIf="graphData && graphData.nodes.length > 0">
          <button
            class="filter-btn"
            [class.active]="selectedClassFilter === 'all'"
            (click)="setFilter('all')"
          >
            All Nodes ({{ graphData.nodes.length }})
          </button>
          <button
            class="filter-btn verifiable"
            [class.active]="selectedClassFilter === 'verifiable'"
            (click)="setFilter('verifiable')"
          >
            Verifiable
          </button>
          <button
            class="filter-btn attested"
            [class.active]="selectedClassFilter === 'attested'"
            (click)="setFilter('attested')"
          >
            Attested
          </button>
          <button
            class="filter-btn derived"
            [class.active]="selectedClassFilter === 'derived'"
            (click)="setFilter('derived')"
          >
            Quarantined (Derived)
          </button>
        </div>
      </div>

      <!-- Empty State if no nodes exist -->
      <div *ngIf="!graphData || graphData.nodes.length === 0" class="empty-graph glass-panel">
        <div class="empty-icon">🕸️</div>
        <h3>Evidence Graph is Empty</h3>
        <p class="empty-sub">
          Your career evidence graph will appear here as soon as you upload a resume or record accomplishment statements in the <strong>Candidate Profile</strong> tab.
        </p>
      </div>

      <!-- Graph Canvas Visualizer Layout -->
      <div *ngIf="graphData && graphData.nodes.length > 0" class="canvas-layout">
        <!-- Main Visual Graph SVG Area -->
        <div class="svg-stage glass-panel">
          <div class="quarantine-banner">
            <div class="quarantine-box">
              <span class="lock-icon">🔒</span>
              <strong>Derived Quarantine Zone (Guardrail G1):</strong>
              Unconfirmed AI inferences are strictly barred from composer retrieval until user confirmation.
            </div>
          </div>

          <svg class="graph-svg" viewBox="0 0 900 520">
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#4b5563" />
              </marker>
            </defs>

            <!-- Quarantine Zone Visual Divider -->
            <rect x="620" y="20" width="260" height="480" rx="12" class="quarantine-rect" />
            <text x="635" y="45" class="quarantine-label">DERIVED QUARANTINE ZONE</text>

            <!-- Edges -->
            <g class="edges-layer">
              <line
                *ngFor="let edge of displayedEdges"
                [attr.x1]="getNodePosition(edge.source).x"
                [attr.y1]="getNodePosition(edge.source).y"
                [attr.x2]="getNodePosition(edge.target).x"
                [attr.y2]="getNodePosition(edge.target).y"
                stroke="#374151"
                stroke-width="1.5"
                marker-end="url(#arrow)"
              />
            </g>

            <!-- Nodes -->
            <g class="nodes-layer">
              <g
                *ngFor="let node of displayedNodes"
                class="node-group"
                [class.selected]="selectedNode?.id === node.id"
                [attr.transform]="'translate(' + getNodePosition(node.id).x + ',' + getNodePosition(node.id).y + ')'"
                (click)="selectNode(node)"
              >
                <circle
                  r="20"
                  [attr.fill]="getNodeColor(node)"
                  [attr.stroke]="selectedNode?.id === node.id ? '#ffffff' : getNodeStroke(node)"
                  stroke-width="2"
                />
                <text text-anchor="middle" dy="4" class="node-icon">
                  {{ getNodeIcon(node) }}
                </text>
                <text text-anchor="middle" dy="34" class="node-label">
                  {{ truncate(node.claim || node.title || node.raw || node.name || node.id, 22) }}
                </text>
              </g>
            </g>
          </svg>
        </div>

        <!-- Node Inspector Panel -->
        <div class="inspector-panel glass-panel">
          <h3>Node Inspector</h3>
          <p class="subtext">Click any node in the graph to examine its verified metadata and provenance.</p>

          <div *ngIf="selectedNode; else noNodeSelected" class="node-details animate-fade-in">
            <div class="detail-badge-row">
              <span class="badge" [ngClass]="getAttestationClassBadge(selectedNode)">
                {{ selectedNode.attestation_class || selectedNode.type }}
              </span>
              <span class="node-type-label">Type: {{ selectedNode.type | uppercase }}</span>
            </div>

            <div class="detail-block">
              <div class="detail-label">Node Identifier</div>
              <div class="detail-value"><code>{{ selectedNode.id }}</code></div>
            </div>

            <div class="detail-block" *ngIf="selectedNode.claim">
              <div class="detail-label">Accomplishment Claim</div>
              <div class="detail-value">{{ selectedNode.claim }}</div>
            </div>

            <div class="detail-block" *ngIf="selectedNode.title">
              <div class="detail-label">Artifact Title</div>
              <div class="detail-value">{{ selectedNode.title }}</div>
            </div>

            <div class="detail-block" *ngIf="selectedNode.raw">
              <div class="detail-label">Verbatim Statement (Invariant 3)</div>
              <div class="detail-value statement-raw">"{{ selectedNode.raw }}"</div>
            </div>

            <div class="detail-block" *ngIf="selectedNode.skills?.length">
              <div class="detail-label">Demonstrated Skills</div>
              <div class="skills-wrap">
                <span *ngFor="let s of selectedNode.skills" class="badge badge-corroborated">{{ s }}</span>
              </div>
            </div>

            <div class="detail-block" *ngIf="selectedNode.is_quarantined">
              <div class="alert-quarantine">
                🔒 <strong>Quarantined Node (G1):</strong> This accomplishment was inferred by an AI model and is blocked from composer query retrieval until user confirmation.
              </div>
            </div>
          </div>

          <ng-template #noNodeSelected>
            <div class="empty-inspector">
              <span class="empty-icon">👆</span>
              <div>Select a node on the canvas to inspect its details and provenance chain.</div>
            </div>
          </ng-template>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .graph-container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 24px 48px;
    }
    .view-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 20px;
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
    .filter-group {
      display: flex;
      gap: 8px;
    }
    .filter-btn {
      padding: 6px 12px;
      border-radius: 6px;
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      font-size: 0.75rem;
      font-weight: 600;
      cursor: pointer;
    }
    .filter-btn.active {
      background: #1f293d;
      color: var(--text-primary);
      border-color: var(--accent-teal);
    }
    .filter-btn.verifiable.active { border-color: #2dd4bf; color: #2dd4bf; }
    .filter-btn.attested.active { border-color: #a78bfa; color: #a78bfa; }
    .filter-btn.derived.active { border-color: #fb7185; color: #fb7185; }

    .empty-graph {
      text-align: center;
      padding: 60px 20px;
      color: var(--text-muted);
    }
    .empty-icon {
      font-size: 3rem;
      margin-bottom: 12px;
    }
    .empty-graph h3 {
      font-size: 1.2rem;
      color: var(--text-secondary);
      margin-bottom: 6px;
    }
    .empty-sub {
      font-size: 0.9rem;
      max-width: 500px;
      margin: 0 auto;
    }

    .canvas-layout {
      display: grid;
      grid-template-columns: 1fr 340px;
      gap: 20px;
    }
    @media (max-width: 900px) {
      .canvas-layout { grid-template-columns: 1fr; }
    }
    .svg-stage {
      padding: 16px;
      position: relative;
      overflow: hidden;
    }
    .quarantine-banner {
      margin-bottom: 12px;
    }
    .quarantine-box {
      font-size: 0.8rem;
      background: rgba(244, 63, 94, 0.08);
      border: 1px dashed rgba(244, 63, 94, 0.3);
      padding: 8px 12px;
      border-radius: 6px;
      color: #fda4af;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .graph-svg {
      width: 100%;
      height: 520px;
      background: var(--bg-dark);
      border-radius: 8px;
    }
    .quarantine-rect {
      fill: rgba(244, 63, 94, 0.03);
      stroke: rgba(244, 63, 94, 0.3);
      stroke-dasharray: 6, 6;
    }
    .quarantine-label {
      fill: #fb7185;
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.05em;
    }
    .node-group {
      cursor: pointer;
      transition: transform 0.15s ease;
    }
    .node-group:hover circle {
      filter: brightness(1.2);
    }
    .node-icon {
      font-size: 0.85rem;
      pointer-events: none;
    }
    .node-label {
      font-size: 0.65rem;
      fill: var(--text-secondary);
      font-family: var(--font-sans);
      pointer-events: none;
    }
    .inspector-panel {
      padding: 20px;
      display: flex;
      flex-direction: column;
    }
    .inspector-panel h3 {
      font-size: 1.1rem;
      color: var(--text-primary);
      margin-bottom: 4px;
    }
    .detail-badge-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border-subtle);
    }
    .node-type-label {
      font-size: 0.75rem;
      color: var(--text-muted);
      font-weight: 600;
    }
    .detail-block {
      margin-bottom: 14px;
    }
    .detail-label {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-bottom: 4px;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .detail-value {
      font-size: 0.875rem;
      color: var(--text-primary);
      line-height: 1.4;
    }
    .statement-raw {
      font-style: italic;
      color: #c4b5fd;
    }
    .skills-wrap {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .alert-quarantine {
      padding: 10px;
      background: rgba(244, 63, 94, 0.1);
      border: 1px solid rgba(244, 63, 94, 0.3);
      color: #fb7185;
      border-radius: 6px;
      font-size: 0.8rem;
    }
    .empty-inspector {
      margin-top: 40px;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.85rem;
    }
    .empty-icon {
      font-size: 2rem;
      display: block;
      margin-bottom: 8px;
    }
  `],
})
export class GraphViewComponent implements OnInit {
  graphData: GraphData | null = null;
  selectedClassFilter: string = 'all';
  selectedNode: EvidenceNode | null = null;

  private nodePositions: Record<string, { x: number; y: number }> = {};

  constructor(private apiService: ApiService) {}

  async ngOnInit(): Promise<void> {
    await this.loadGraph();
  }

  async loadGraph(): Promise<void> {
    this.graphData = await this.apiService.getEvidenceGraph();
    this.layoutNodes();
    if (this.graphData?.nodes?.length > 0) {
      this.selectedNode = this.graphData.nodes[0];
    }
  }

  setFilter(filter: string): void {
    this.selectedClassFilter = filter;
  }

  get displayedNodes(): EvidenceNode[] {
    if (!this.graphData?.nodes) return [];
    if (this.selectedClassFilter === 'all') return this.graphData.nodes;
    return this.graphData.nodes.filter(
      (n) => n.attestation_class === this.selectedClassFilter
    );
  }

  get displayedEdges(): EvidenceEdge[] {
    if (!this.graphData?.edges) return [];
    const validNodeIds = new Set(this.displayedNodes.map((n) => n.id));
    return this.graphData.edges.filter(
      (e) => validNodeIds.has(e.source) && validNodeIds.has(e.target)
    );
  }

  layoutNodes(): void {
    if (!this.graphData?.nodes) return;
    this.nodePositions = {};

    let artIndex = 0;
    let accIndex = 0;
    let skillIndex = 0;
    let derivedIndex = 0;

    for (const node of this.graphData.nodes) {
      if (node.is_quarantined || node.attestation_class === 'derived') {
        this.nodePositions[node.id] = {
          x: 750,
          y: 120 + derivedIndex * 100,
        };
        derivedIndex++;
      } else if (node.type === 'artifact' || node.type === 'statement') {
        this.nodePositions[node.id] = {
          x: 100,
          y: 90 + artIndex * 90,
        };
        artIndex++;
      } else if (node.type === 'accomplishment') {
        this.nodePositions[node.id] = {
          x: 320,
          y: 100 + accIndex * 110,
        };
        accIndex++;
      } else {
        this.nodePositions[node.id] = {
          x: 520,
          y: 80 + skillIndex * 70,
        };
        skillIndex++;
      }
    }
  }

  getNodePosition(nodeId: string): { x: number; y: number } {
    return this.nodePositions[nodeId] || { x: 300, y: 200 };
  }

  getNodeColor(node: EvidenceNode): string {
    if (node.is_quarantined || node.attestation_class === 'derived') return '#881337';
    if (node.attestation_class === 'verifiable') return '#115e59';
    if (node.attestation_class === 'attested') return '#581c87';
    if (node.type === 'skill') return '#78350f';
    return '#1e3a8a';
  }

  getNodeStroke(node: EvidenceNode): string {
    if (node.is_quarantined || node.attestation_class === 'derived') return '#fb7185';
    if (node.attestation_class === 'verifiable') return '#2dd4bf';
    if (node.attestation_class === 'attested') return '#a78bfa';
    if (node.type === 'skill') return '#fbbf24';
    return '#60a5fa';
  }

  getNodeIcon(node: EvidenceNode): string {
    if (node.is_quarantined || node.attestation_class === 'derived') return '🔒';
    if (node.type === 'artifact') return '📄';
    if (node.type === 'statement') return '💬';
    if (node.type === 'accomplishment') return '⭐';
    if (node.type === 'skill') return '⚡';
    return '📊';
  }

  getAttestationClassBadge(node: EvidenceNode): string {
    if (node.attestation_class === 'verifiable') return 'badge-verifiable';
    if (node.attestation_class === 'attested') return 'badge-attested';
    if (node.attestation_class === 'derived') return 'badge-derived';
    return 'badge-corroborated';
  }

  selectNode(node: EvidenceNode): void {
    this.selectedNode = node;
  }

  truncate(str: string, len: number): string {
    return str.length > len ? str.substring(0, len) + '...' : str;
  }
}
