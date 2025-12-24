/**
 * Company Profile API functions
 *
 * Handles company profile, NAICS codes, certifications, and onboarding
 */

import { apiClient } from './client';

// =============================================================================
// Types
// =============================================================================

export interface CompanyProfile {
  id: string;
  user_id: string;
  company_name: string;
  uei: string | null;
  duns_number: string | null;
  cage_code: string | null;
  business_size: string | null;
  employee_count: number | null;
  annual_revenue: number | null;
  min_contract_value: number | null;
  max_contract_value: number | null;
  typical_contract_size: string | null;
  facility_clearance: string | null;
  has_sci_capability: boolean;
  pref_firm_fixed_price: number;
  pref_time_materials: number;
  pref_cost_plus: number;
  pref_idiq: number;
  pref_sole_source: number;
  headquarters_state: string | null;
  geographic_preference: string;
  preferred_states: string[] | null;
  willing_to_travel: boolean;
  min_days_to_respond: number;
  can_rush_proposals: boolean;
  onboarding_completed: boolean;
  onboarding_step: number;
  profile_completeness: number;
  created_at: string;
  updated_at: string;
}

export interface CompanyNAICS {
  id: string;
  naics_code: string;
  naics_description: string | null;
  experience_level: string;
  is_primary: boolean;
  years_experience: number | null;
  contracts_won: number;
  created_at: string;
}

export interface CompanyCertification {
  id: string;
  certification_type: string;
  certification_number: string | null;
  certifying_agency: string | null;
  issue_date: string | null;
  expiration_date: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface PastPerformance {
  id: string;
  contract_title: string;
  description: string | null;
  contract_number: string | null;
  task_order_number: string | null;
  piid: string | null;
  agency_name: string | null;
  naics_code: string | null;
  contract_value: number | null;
  period_of_performance_months: number | null;
  start_date: string | null;
  end_date: string | null;
  role: string;
  performance_rating: string | null;
  contract_type: string | null;
  set_aside_type: string | null;
  created_at: string;
}

export interface OnboardingStatus {
  onboarding_completed: boolean;
  onboarding_step: number;
  profile_completeness: number;
  has_profile: boolean;
  has_naics: boolean;
  has_certifications: boolean;
}

// =============================================================================
// Profile API
// =============================================================================

export async function getCompanyProfile(): Promise<CompanyProfile | null> {
  const response = await apiClient.get<CompanyProfile | null>('/company/profile');
  return response.data;
}

export async function createCompanyProfile(data: Partial<CompanyProfile>): Promise<CompanyProfile> {
  const response = await apiClient.post<CompanyProfile>('/company/profile', data);
  return response.data;
}

export async function updateCompanyProfile(data: Partial<CompanyProfile>): Promise<CompanyProfile> {
  const response = await apiClient.patch<CompanyProfile>('/company/profile', data);
  return response.data;
}

// =============================================================================
// NAICS API
// =============================================================================

export async function listNAICSCodes(): Promise<CompanyNAICS[]> {
  const response = await apiClient.get<CompanyNAICS[]>('/company/profile/naics');
  return response.data;
}

export async function addNAICSCode(data: {
  naics_code: string;
  naics_description?: string;
  experience_level?: string;
  is_primary?: boolean;
  years_experience?: number;
  contracts_won?: number;
}): Promise<CompanyNAICS> {
  const response = await apiClient.post<CompanyNAICS>('/company/profile/naics', data);
  return response.data;
}

export async function deleteNAICSCode(naicsId: string): Promise<void> {
  await apiClient.delete(`/company/profile/naics/${naicsId}`);
}

// =============================================================================
// Certifications API
// =============================================================================

export async function listCertifications(): Promise<CompanyCertification[]> {
  const response = await apiClient.get<CompanyCertification[]>('/company/profile/certifications');
  return response.data;
}

export async function addCertification(data: {
  certification_type: string;
  certification_number?: string;
  certifying_agency?: string;
  issue_date?: string;
  expiration_date?: string;
  is_active?: boolean;
}): Promise<CompanyCertification> {
  const response = await apiClient.post<CompanyCertification>('/company/profile/certifications', data);
  return response.data;
}

export async function deleteCertification(certId: string): Promise<void> {
  await apiClient.delete(`/company/profile/certifications/${certId}`);
}

// =============================================================================
// Past Performance API
// =============================================================================

export async function listPastPerformance(): Promise<PastPerformance[]> {
  const response = await apiClient.get<PastPerformance[]>('/company/profile/past-performance');
  return response.data;
}

export async function addPastPerformance(data: Partial<PastPerformance>): Promise<PastPerformance> {
  const response = await apiClient.post<PastPerformance>('/company/profile/past-performance', data);
  return response.data;
}

export async function deletePastPerformance(ppId: string): Promise<void> {
  await apiClient.delete(`/company/profile/past-performance/${ppId}`);
}

// =============================================================================
// Onboarding API
// =============================================================================

export async function getOnboardingStatus(): Promise<OnboardingStatus> {
  const response = await apiClient.get<OnboardingStatus>('/company/onboarding/status');
  return response.data;
}

export async function completeOnboarding(): Promise<CompanyProfile> {
  const response = await apiClient.post<CompanyProfile>('/company/onboarding/complete');
  return response.data;
}

export async function skipOnboarding(): Promise<{ message: string }> {
  const response = await apiClient.post<{ message: string }>('/company/onboarding/skip');
  return response.data;
}

// =============================================================================
// Scoring API
// =============================================================================

export interface ScoreCalculationResult {
  message: string;
  opportunities_scored: number;
  total_opportunities: number;
  score_distribution: {
    high_scores: number;
    medium_scores: number;
    low_scores: number;
  };
  naics_count: number;
  naics_codes: string[];
  cert_count: number;
  certifications: string[];
  business_size: string | null;
  profile_completeness: number;
  errors: Array<{ opportunity_id: string; notice_id: string; error: string }> | null;
}

export async function calculateScores(): Promise<ScoreCalculationResult> {
  const response = await apiClient.post<ScoreCalculationResult>('/company/scoring/calculate');
  return response.data;
}

export interface ScoringDebugInfo {
  has_profile: boolean;
  profile_id?: string;
  user_id?: string;
  onboarding_completed?: boolean;
  onboarding_step?: number;
  profile_completeness?: number;
  business_size?: string;
  naics_codes?: Array<{ code: string; is_primary: boolean }>;
  naics_codes_list?: string[];
  certifications?: Array<{ type: string; active: boolean }>;
  existing_scores_count?: number;
  sample_scores?: Array<{
    opportunity_id: string;
    overall_score: number;
    capability_score: number;
    capability_breakdown: any;
    eligibility_score: number;
    eligibility_breakdown: any;
    scale_score: number;
    timeline_score: number;
    calculated_at: string | null;
  }>;
  sample_opportunities?: Array<{
    id: string;
    title: string | null;
    naics_code: string | null;
    set_aside_type: string | null;
    contract_type: string | null;
    naics_match: boolean;
    naics_4digit_match: boolean;
  }>;
  message?: string;
}

export async function getScoringDebug(): Promise<ScoringDebugInfo> {
  const response = await apiClient.get<ScoringDebugInfo>('/company/scoring/debug');
  return response.data;
}

// =============================================================================
// Capability Statement API
// =============================================================================

export interface CapabilityStatement {
  id: string;
  name: string;
  description: string | null;
  core_competencies: string[] | null;
  differentiators: string[] | null;
  keywords: string[] | null;
  target_naics_codes: string[] | null;
  target_agencies: string[] | null;
  file_url: string | null;
  file_name: string | null;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export async function listCapabilityStatements(): Promise<CapabilityStatement[]> {
  const response = await apiClient.get<CapabilityStatement[]>('/company/profile/capability-statements');
  return response.data;
}

export async function uploadCapabilityStatement(
  file: File,
  name?: string,
  isDefault: boolean = false
): Promise<CapabilityStatement> {
  const formData = new FormData();
  formData.append('file', file);
  if (name) {
    formData.append('name', name);
  }
  formData.append('is_default', String(isDefault));

  const response = await apiClient.post<CapabilityStatement>(
    '/company/profile/capability-statements/upload',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
}

export async function createCapabilityStatement(data: {
  name: string;
  description?: string;
  full_text?: string;
  core_competencies?: string[];
  differentiators?: string[];
  keywords?: string[];
  target_naics_codes?: string[];
  target_agencies?: string[];
  is_default?: boolean;
}): Promise<CapabilityStatement> {
  const response = await apiClient.post<CapabilityStatement>('/company/profile/capability-statements', data);
  return response.data;
}

export async function deleteCapabilityStatement(capId: string): Promise<void> {
  await apiClient.delete(`/company/profile/capability-statements/${capId}`);
}
