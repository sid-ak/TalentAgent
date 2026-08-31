/**
 * Data models and interfaces for the TalentAgent user interface.
 */

export type AttestationClass = 'verifiable' | 'corroborated' | 'attested' | 'derived';

export type NodeType = 'artifact' | 'statement' | 'accomplishment' | 'skill' | 'metric';

export interface Identity {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  location?: string;
}

export interface Links {
  github?: string;
  linkedin?: string;
  portfolio?: string;
}

export interface Materials {
  resume?: string;
  cover_letter?: string;
}

export interface CandidateProfile {
  identity: Identity;
  links: Links;
  resume_filename?: string | null;
  node_count: number;
  has_profile: boolean;
}

export interface EvidenceNode {
  id: string;
  type: NodeType;
  claim?: string;
  title?: string;
  subtype?: string;
  raw?: string;
  name?: string;
  value?: number;
  unit?: string;
  skills?: string[];
  evidence?: string[];
  attestation_class?: AttestationClass;
  is_quarantined?: boolean;
  elicited_by?: string;
  url?: string;
  metadata?: Record<string, any>;
  x?: number;
  y?: number;
}

export interface EvidenceEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: EvidenceNode[];
  edges: EvidenceEdge[];
  quarantine_rule?: string;
}

export interface CreditedBullet {
  text: string;
  credits: string[];
  attestation_class: AttestationClass;
  artifacts: string[];
  requirement_ids: string[];
}

export interface Gap {
  requirement_id: string;
  text: string;
  best_available?: string;
  sufficiency: number;
  action: 'FLAG' | 'ELICIT';
  question?: string;
}

export interface Coverage {
  total: number;
  verifiable: number;
  corroborated: number;
  attested: number;
}

export interface ApplicationPackage {
  posting_id: string;
  identity: Identity;
  links?: Links;
  materials?: Materials;
  bullets: CreditedBullet[];
  screening_answers: Array<{
    question: string;
    answer: string;
    credits: string[];
    attestation_class: AttestationClass;
  }>;
  gaps: Gap[];
  coverage: Coverage;
}

export interface MappedField {
  selector: string;
  target_path: string;
  resolved_type: string;
  status: string;
  value?: string;
}

export interface ATSFillResult {
  platform: string;
  completion_rate: number;
  passes_required: number;
  total_fields: number;
  mapped_fields: MappedField[];
  halt_reason?: string | null;
  human_review_required: boolean;
  guardrail_g3: string;
}

export interface GuardrailInfo {
  name: string;
  active: boolean;
}

export interface SystemStatus {
  status: string;
  system: string;
  backend: string;
  gemini_connected: boolean;
  guardrails: Record<string, GuardrailInfo>;
  quotas: {
    tier_1_used: number;
    tier_1_limit: number;
    tier_2_used: number;
    tier_2_limit: number;
  };
  platforms: string[];
}
