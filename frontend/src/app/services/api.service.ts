/**
 * REST API client service for TalentAgent UI with offline fixture fallbacks.
 */

import { Injectable } from '@angular/core';
import {
  ApplicationPackage,
  ATSFillResult,
  CandidateProfile,
  GraphData,
  SystemStatus,
} from '../models/talentagent.models';

@Injectable({
  providedIn: 'root',
})
export class ApiService {
  private baseUrl = '';
  public isConnected = false;

  constructor() {
    this.checkHealth();
  }

  async checkHealth(): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/api/status`, { method: 'GET' });
      if (res.ok) {
        this.isConnected = true;
        return true;
      }
    } catch {
      this.isConnected = false;
    }
    return false;
  }

  async getStatus(): Promise<SystemStatus> {
    try {
      const res = await fetch(`${this.baseUrl}/api/status`);
      if (res.ok) {
        this.isConnected = true;
        return await res.json();
      }
    } catch {
      this.isConnected = false;
    }

    return {
      status: 'healthy (offline mode)',
      phase: '2.5-Demo',
      backend: 'mock-fixtures',
      gemini_connected: false,
      guardrails: {
        G1: { name: 'No model-originated claims (Quarantine enforced)', active: true },
        G2: { name: 'No uncredited lines (Schema rejection layer)', active: true },
        G3: { name: 'No irreversible autonomy (Human-only submit)', active: true },
        G4: { name: 'No suppression by self-derived signal', active: true },
        G5: { name: 'No prohibited automation (Allowlist enforced)', active: true },
        G6: { name: 'No credential handling (Zero password tools)', active: true },
        G7: { name: 'Untrusted content treated as data', active: true },
      },
      quotas: {
        tier_1_used: 12,
        tier_1_limit: 1000,
        tier_2_used: 4,
        tier_2_limit: 250,
      },
      platforms: ['greenhouse', 'lever', 'ashby'],
    };
  }

  async getProfiles(): Promise<CandidateProfile[]> {
    try {
      const res = await fetch(`${this.baseUrl}/api/profiles`);
      if (res.ok) {
        const data = await res.json();
        return data.profiles;
      }
    } catch {
      // offline fallback
    }

    return [
      {
        id: 'profile_a',
        name: 'Profile A (Distributed Systems Engineer)',
        type: 'Technical / Repository-Backed',
        description: 'Artifact-backed engineering profile with commits, PRs, and system design docs.',
        node_count: 28,
        attestation_classes: ['verifiable', 'corroborated'],
        identity: {
          first_name: 'Jordan',
          last_name: 'Lee',
          email: 'jordan.lee@example.com',
          location: 'Seattle, WA',
        },
        links: {
          github: 'https://github.com/jordanlee',
          linkedin: 'https://linkedin.com/in/jordanlee',
        },
        materials: {
          resume: 'Jordan_Lee_Resume.pdf',
        },
      },
      {
        id: 'profile_b',
        name: 'Profile B (Principal Product Lead)',
        type: 'Non-Engineering / Statement-Backed',
        description: '100% attested statements with zero public software artifacts, proving no hallucination for non-coders.',
        node_count: 18,
        attestation_classes: ['attested'],
        identity: {
          first_name: 'Morgan',
          last_name: 'Taylor',
          email: 'morgan.taylor@example.com',
          location: 'New York, NY',
        },
        links: {
          linkedin: 'https://linkedin.com/in/morgantaylor',
        },
        materials: {
          resume: 'Morgan_Taylor_CV.pdf',
        },
      },
      {
        id: 'custom',
        name: 'Custom Candidate Profile',
        type: 'User-Managed Profile',
        description: 'Upload your resume PDF, add GitHub repos, or enter accomplishment statements directly in your own words.',
        node_count: 6,
        attestation_classes: ['verifiable', 'attested'],
        identity: {
          first_name: 'Alex',
          last_name: 'Rivers',
          email: 'alex.rivers@example.com',
          location: 'San Francisco, CA',
        },
        links: {
          github: 'https://github.com/alexrivers',
          linkedin: 'https://linkedin.com/in/alexrivers',
        },
        materials: {
          resume: 'Alex_Rivers_Resume.pdf',
        },
      },
    ];
  }

  async getEvidenceGraph(profileId: string): Promise<GraphData> {
    try {
      const res = await fetch(`${this.baseUrl}/api/evidence-graph?profile_id=${profileId}`);
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // offline fallback
    }

    if (profileId === 'profile_b') {
      return {
        profile_id: 'profile_b',
        quarantine_rule: 'G1: derived nodes are strictly quarantined from composer retrieval',
        nodes: [
          { id: 'stm_b1', type: 'statement', raw: 'Led product strategy and roadmap for enterprise multi-tenant analytics platform serving 40k weekly active users.', attestation_class: 'attested' },
          { id: 'stm_b2', type: 'statement', raw: 'Negotiated cross-functional alignment across 14 executive stakeholders to launch privacy-first data ingestion.', attestation_class: 'attested' },
          { id: 'acc_b1', type: 'accomplishment', claim: 'Directed multi-tenant enterprise analytics roadmap reaching 40k weekly active users', skills: ['skill_product_strategy', 'skill_stakeholder_management'], attestation_class: 'attested', evidence: ['stm_b1'] },
          { id: 'acc_b2', type: 'accomplishment', claim: 'Aligned 14 executive stakeholders to ship zero-trust privacy data architecture', skills: ['skill_stakeholder_management', 'skill_operations'], attestation_class: 'attested', evidence: ['stm_b2'] },
          { id: 'skill_product_strategy', type: 'skill', name: 'Product Strategy' },
          { id: 'skill_stakeholder_management', type: 'skill', name: 'Stakeholder Management' },
          { id: 'skill_operations', type: 'skill', name: 'Operations' },
        ],
        edges: [
          { source: 'stm_b1', target: 'acc_b1', type: 'evidences' },
          { source: 'stm_b2', target: 'acc_b2', type: 'evidences' },
          { source: 'acc_b1', target: 'skill_product_strategy', type: 'demonstrates' },
          { source: 'acc_b1', target: 'skill_stakeholder_management', type: 'demonstrates' },
          { source: 'acc_b2', target: 'skill_stakeholder_management', type: 'demonstrates' },
        ],
      };
    }

    // Default Profile A / Custom
    return {
      profile_id: profileId,
      quarantine_rule: 'G1: derived nodes are strictly quarantined from composer retrieval',
      nodes: [
        { id: 'art_pr_412', type: 'artifact', subtype: 'PR', title: 'PR #412: Distributed Pub/Sub event bus', url: 'https://github.com/jordanlee/event-bus/pull/412', metadata: { summary: 'Zero data loss message pipeline handling 50k events/sec.' } },
        { id: 'art_pr_419', type: 'artifact', subtype: 'PR', title: 'PR #419: JWT authentication & rate limiting', url: 'https://github.com/jordanlee/event-bus/pull/419', metadata: { summary: 'Implemented token rotation and Redis rate limiter.' } },
        { id: 'art_doc_arch', type: 'artifact', subtype: 'DOC', title: 'RFC-089: Zero-downtime database migration strategy', url: 'https://docs.google.com/document/d/rfc089', metadata: { summary: 'Engineered dual-write shadow pipeline for PostgreSQL migration.' } },
        { id: 'acc_1', type: 'accomplishment', claim: 'Engineered high-throughput distributed pub/sub event pipeline processing 50k events/sec with zero packet loss', skills: ['skill_python', 'skill_distributed_systems', 'skill_pubsub'], attestation_class: 'verifiable', evidence: ['art_pr_412'] },
        { id: 'acc_2', type: 'accomplishment', claim: 'Architected zero-downtime database migration pipeline maintaining continuous uptime across 12M customer records', skills: ['skill_python', 'skill_distributed_systems', 'skill_migration'], attestation_class: 'verifiable', evidence: ['art_doc_arch'] },
        { id: 'acc_3', type: 'accomplishment', claim: 'Implemented stateless JWT authentication layer and Redis rate limiting reducing unauthorized latency spikes by 60%', skills: ['skill_python', 'skill_auth'], attestation_class: 'verifiable', evidence: ['art_pr_419'] },
        { id: 'acc_derived_candidate', type: 'accomplishment', claim: 'Inferred experience leading global cloud migration initiatives [UNCONFIRMED MODEL INFERENCE]', skills: ['skill_kubernetes'], attestation_class: 'derived', is_quarantined: true, evidence: ['art_doc_arch'] },
        { id: 'skill_python', type: 'skill', name: 'Python' },
        { id: 'skill_distributed_systems', type: 'skill', name: 'Distributed Systems' },
        { id: 'skill_pubsub', type: 'skill', name: 'Pub/Sub' },
        { id: 'skill_auth', type: 'skill', name: 'Authentication' },
        { id: 'skill_migration', type: 'skill', name: 'Data Migration' },
        { id: 'skill_kubernetes', type: 'skill', name: 'Kubernetes' },
      ],
      edges: [
        { source: 'art_pr_412', target: 'acc_1', type: 'evidences' },
        { source: 'art_doc_arch', target: 'acc_2', type: 'evidences' },
        { source: 'art_pr_419', target: 'acc_3', type: 'evidences' },
        { source: 'art_doc_arch', target: 'acc_derived_candidate', type: 'evidences' },
        { source: 'acc_1', target: 'skill_python', type: 'demonstrates' },
        { source: 'acc_1', target: 'skill_distributed_systems', type: 'demonstrates' },
        { source: 'acc_1', target: 'skill_pubsub', type: 'demonstrates' },
        { source: 'acc_2', target: 'skill_distributed_systems', type: 'demonstrates' },
        { source: 'acc_2', target: 'skill_migration', type: 'demonstrates' },
        { source: 'acc_3', target: 'skill_auth', type: 'demonstrates' },
      ],
    };
  }

  async extractRequirements(postingText: string): Promise<string[]> {
    try {
      const res = await fetch(`${this.baseUrl}/api/extract-requirements`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ posting_text: postingText }),
      });
      if (res.ok) {
        const data = await res.json();
        return data.requirements;
      }
    } catch {
      // fallback
    }

    return postingText
      .split('\n')
      .map((l) => l.replace(/^[•\-\*\d\.]+\s*/, '').trim())
      .filter((l) => l.length > 15);
  }

  async composePackage(profileId: string, postingId: string, requirements: string[], identity?: any): Promise<ApplicationPackage> {
    try {
      const res = await fetch(`${this.baseUrl}/api/compose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile_id: profileId,
          posting_id: postingId,
          requirements: requirements,
          identity: identity,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        return data.package;
      }
    } catch {
      // offline fallback
    }

    // Mock Offline Composed Package
    const isAdversarial = postingId.includes('adversarial') || requirements.some(r => r.toLowerCase().includes('quantum') || r.toLowerCase().includes('blockchain'));
    
    if (isAdversarial) {
      return {
        posting_id: postingId,
        identity: identity || { first_name: 'Test', last_name: 'Candidate', email: 'test@example.com' },
        bullets: [],
        screening_answers: [],
        gaps: requirements.map((req, idx) => ({
          requirement_id: `req_adv_${idx}`,
          text: req,
          sufficiency: 0.0,
          action: 'ELICIT',
          question: `Nothing in the evidence graph touches '${req}'. Have you worked on this, over what timeframe, what was your specific role vs the team's, and what quantitative outcome resulted?`,
        })),
        coverage: {
          total: 0.0,
          verifiable: 0.0,
          corroborated: 0.0,
          attested: 0.0,
        },
      };
    }

    return {
      posting_id: postingId,
      identity: identity || { first_name: 'Jordan', last_name: 'Lee', email: 'jordan.lee@example.com' },
      bullets: [
        {
          text: 'Engineered high-throughput distributed pub/sub event pipeline processing 50k events/sec with zero packet loss.',
          credits: ['acc_1'],
          attestation_class: 'verifiable',
          artifacts: ['art_pr_412'],
          requirement_ids: ['req_1'],
        },
        {
          text: 'Architected zero-downtime database migration pipeline maintaining continuous uptime across 12M customer records.',
          credits: ['acc_2'],
          attestation_class: 'verifiable',
          artifacts: ['art_doc_arch'],
          requirement_ids: ['req_2'],
        },
      ],
      screening_answers: [
        {
          question: 'Do you have experience with Python and distributed systems?',
          answer: 'Yes, architected distributed pub/sub event pipelines handling 50k events/sec in Python.',
          credits: ['acc_1'],
          attestation_class: 'verifiable',
        },
      ],
      gaps: [
        {
          requirement_id: 'req_k8s',
          text: '5+ years experience managing Kubernetes cluster orchestration in production',
          sufficiency: 0.0,
          action: 'ELICIT',
          question: "Nothing in the evidence graph touches 'Kubernetes cluster orchestration'. Have you worked on this, over what timeframe, what was your specific role vs the team's, and what quantitative outcome resulted?",
        },
      ],
      coverage: {
        total: 1.0,
        verifiable: 1.0,
        corroborated: 0.0,
        attested: 0.0,
      },
    };
  }

  async promoteStatement(profileId: string, answer: string, requirementText?: string, skills: string[] = []): Promise<any> {
    try {
      const res = await fetch(`${this.baseUrl}/api/promote-statement`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile_id: profileId,
          answer: answer,
          requirement_text: requirementText,
          skills: skills,
        }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // offline fallback
    }

    return {
      status: 'promoted',
      statement_id: `stm_${Date.now() % 10000}`,
      accomplishment_id: `acc_${Date.now() % 10000}`,
      raw_text: answer,
      attestation_class: 'attested',
    };
  }

  async uploadResume(contentBase64?: string, text?: string, filename = 'resume.pdf'): Promise<any> {
    try {
      const res = await fetch(`${this.baseUrl}/api/profile/upload-resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content_base64: contentBase64,
          text: text,
          filename: filename,
        }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // offline fallback
    }

    return {
      status: 'success',
      filename: filename,
      extracted_length: text ? text.length : 1200,
      nodes_added: 4,
      total_custom_nodes: 10,
    };
  }

  async addStatement(rawText: string, skills: string[] = []): Promise<any> {
    try {
      const res = await fetch(`${this.baseUrl}/api/profile/add-statement`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_text: rawText, skills }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // offline fallback
    }

    return {
      status: 'added',
      statement_id: `stm_${Date.now() % 10000}`,
      accomplishment_id: `acc_${Date.now() % 10000}`,
      attestation_class: 'attested',
    };
  }

  async syncGithub(username: string, repo: string): Promise<any> {
    try {
      const res = await fetch(`${this.baseUrl}/api/profile/sync-github`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, repo }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // offline fallback
    }

    return {
      status: 'synced',
      artifact_id: `art_gh_${Date.now() % 10000}`,
      accomplishment_id: `acc_gh_${Date.now() % 10000}`,
      attestation_class: 'verifiable',
    };
  }

  async runATSFill(platform: string, pkg: ApplicationPackage): Promise<ATSFillResult> {
    try {
      const res = await fetch(`${this.baseUrl}/api/ats-fill`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform, package: pkg }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // offline fallback
    }

    return {
      platform: platform,
      completion_rate: 1.0,
      passes_required: 1,
      total_fields: 6,
      mapped_fields: [
        { selector: '#first_name', target_path: 'identity.first_name', resolved_type: 'deterministic', status: 'filled', value: pkg.identity.first_name },
        { selector: '#last_name', target_path: 'identity.last_name', resolved_type: 'deterministic', status: 'filled', value: pkg.identity.last_name },
        { selector: '#email', target_path: 'identity.email', resolved_type: 'deterministic', status: 'filled', value: pkg.identity.email },
        { selector: '#phone', target_path: 'identity.phone', resolved_type: 'deterministic', status: 'filled', value: pkg.identity.phone || '415-555-0199' },
        { selector: '#resume_upload', target_path: 'materials.resume', resolved_type: 'deterministic', status: 'filled', value: pkg.materials?.resume || 'Resume.pdf' },
        { selector: '#custom_question_1', target_path: 'screening_answers[0]', resolved_type: 'model_fallback', status: 'filled', value: pkg.screening_answers[0]?.answer || 'Yes, verified experience.' },
      ],
      halt_reason: null,
      human_review_required: true,
      guardrail_g3: 'Autonomous submission is barred; human action required to submit.',
    };
  }
}
