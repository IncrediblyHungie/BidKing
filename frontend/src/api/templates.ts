/**
 * Templates API - Proposal template CRUD and AI generation
 */

import apiClient from './client';

// =============================================================================
// Types
// =============================================================================

export interface TemplateSection {
  heading: string;
  content?: string;
  ai_prompt?: string;
  order: number;
}

export interface ProposalTemplate {
  id: string;
  name: string;
  description?: string;
  template_type: string;
  target_naics_codes?: string[];
  target_agencies?: string[];
  target_keywords?: string[];
  sections?: TemplateSection[];
  raw_content?: string;
  ai_system_prompt?: string;
  use_company_profile: boolean;
  use_past_performance: boolean;
  use_capability_statement: boolean;
  is_active: boolean;
  is_default: boolean;
  is_public: boolean;
  times_used: number;
  last_used_at?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateTemplateRequest {
  name: string;
  description?: string;
  template_type: string;
  target_naics_codes?: string[];
  target_agencies?: string[];
  target_keywords?: string[];
  sections?: TemplateSection[];
  raw_content?: string;
  ai_system_prompt?: string;
  use_company_profile?: boolean;
  use_past_performance?: boolean;
  use_capability_statement?: boolean;
}

export interface UpdateTemplateRequest extends Partial<CreateTemplateRequest> {
  is_active?: boolean;
  is_default?: boolean;
}

export interface GeneratedSection {
  id: string;
  template_id: string;
  opportunity_id?: string;
  section_key: string;
  section_heading?: string;
  generated_content: string;
  edited_content?: string;
  use_edited: boolean;
  model_used?: string;
  tokens_input?: number;
  tokens_output?: number;
  user_rating?: number;
  generated_at: string;
}

export interface GenerateSectionRequest {
  template_id: string;
  opportunity_id?: string;
  section_key: string;
  custom_prompt?: string;
}

export interface QuickGenerateResponse {
  section_type: string;
  content: string;
  tokens_input?: number;
  tokens_output?: number;
  generated_at: string;
}

export interface DefaultTemplate {
  id: string;
  name: string;
  template_type: string;
  description: string;
  sections: TemplateSection[];
}

// =============================================================================
// Template CRUD
// =============================================================================

export const getTemplates = async (params?: {
  template_type?: string;
  include_public?: boolean;
}): Promise<ProposalTemplate[]> => {
  const response = await apiClient.get('/proposals/templates', { params });
  return response.data;
};

export const getTemplate = async (id: string): Promise<ProposalTemplate> => {
  const response = await apiClient.get(`/proposals/templates/${id}`);
  return response.data;
};

export const createTemplate = async (data: CreateTemplateRequest): Promise<ProposalTemplate> => {
  const response = await apiClient.post('/proposals/templates', data);
  return response.data;
};

export const updateTemplate = async (
  id: string,
  data: UpdateTemplateRequest
): Promise<ProposalTemplate> => {
  const response = await apiClient.put(`/proposals/templates/${id}`, data);
  return response.data;
};

export const deleteTemplate = async (id: string): Promise<void> => {
  await apiClient.delete(`/proposals/templates/${id}`);
};

// =============================================================================
// Default Templates
// =============================================================================

export const getDefaultTemplates = async (): Promise<{ defaults: DefaultTemplate[] }> => {
  const response = await apiClient.get('/proposals/templates/defaults/list');
  return response.data;
};

// =============================================================================
// Generated Sections
// =============================================================================

export const getGeneratedSections = async (
  templateId: string,
  opportunityId?: string
): Promise<GeneratedSection[]> => {
  const params = opportunityId ? { opportunity_id: opportunityId } : {};
  const response = await apiClient.get(`/proposals/templates/${templateId}/sections`, { params });
  return response.data;
};

export const updateGeneratedSection = async (
  sectionId: string,
  data: {
    edited_content?: string;
    use_edited?: boolean;
    user_rating?: number;
    feedback_notes?: string;
  }
): Promise<GeneratedSection> => {
  const response = await apiClient.patch(`/proposals/sections/${sectionId}`, data);
  return response.data;
};

export const deleteGeneratedSection = async (sectionId: string): Promise<void> => {
  await apiClient.delete(`/proposals/sections/${sectionId}`);
};

// =============================================================================
// AI Generation
// =============================================================================

export const generateSection = async (
  request: GenerateSectionRequest
): Promise<GeneratedSection> => {
  const response = await apiClient.post('/proposals/generate', request);
  return response.data;
};

export const generateQuickSection = async (params: {
  template_type: string;
  opportunity_id?: string;
  custom_prompt?: string;
}): Promise<QuickGenerateResponse> => {
  const response = await apiClient.post('/proposals/generate-quick', null, { params });
  return response.data;
};

// =============================================================================
// Template Type Helpers
// =============================================================================

export const TEMPLATE_TYPES = [
  { value: 'technical_approach', label: 'Technical Approach' },
  { value: 'past_performance', label: 'Past Performance' },
  { value: 'management_approach', label: 'Management Approach' },
  { value: 'key_personnel', label: 'Key Personnel' },
  { value: 'price_cost', label: 'Price/Cost' },
  { value: 'executive_summary', label: 'Executive Summary' },
  { value: 'full_proposal', label: 'Full Proposal' },
] as const;

export const getTemplateTypeLabel = (type: string): string => {
  return TEMPLATE_TYPES.find(t => t.value === type)?.label || type;
};
