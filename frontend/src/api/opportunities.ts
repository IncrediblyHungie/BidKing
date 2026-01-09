/**
 * Opportunities API calls
 */

import apiClient from './client';
import {
  Opportunity,
  OpportunityListResponse,
  OpportunitySearchParams,
  OpportunityStats,
  SavedOpportunity,
  SavedOpportunityUpdate,
  PipelineStats,
} from '../types';

export const opportunitiesApi = {
  /**
   * Search and list opportunities
   */
  list: async (params: OpportunitySearchParams = {}): Promise<OpportunityListResponse> => {
    const response = await apiClient.get('/opportunities', { params });
    return response.data;
  },

  /**
   * Get opportunity by ID
   */
  get: async (id: string): Promise<Opportunity> => {
    const response = await apiClient.get(`/opportunities/${id}`);
    return response.data;
  },

  /**
   * Get opportunity analysis (score explanation)
   */
  getAnalysis: async (id: string): Promise<{
    opportunity_id: string;
    title: string;
    likelihood_score: number;
    score_category: string;
    score_reasons: string[];
  }> => {
    const response = await apiClient.get(`/opportunities/${id}/analysis`);
    return response.data;
  },

  /**
   * Get opportunity statistics
   */
  getStats: async (): Promise<OpportunityStats> => {
    const response = await apiClient.get('/opportunities/stats');
    return response.data;
  },

  /**
   * List saved opportunities
   */
  listSaved: async (statusFilter?: string): Promise<SavedOpportunity[]> => {
    const params = statusFilter ? { status_filter: statusFilter } : {};
    const response = await apiClient.get('/opportunities/saved/list', { params });
    return response.data;
  },

  /**
   * Save an opportunity
   */
  save: async (data: {
    opportunity_id: string;
    notes?: string;
    status?: string;
    priority?: number;
  }): Promise<SavedOpportunity> => {
    const response = await apiClient.post('/opportunities/saved', data);
    return response.data;
  },

  /**
   * Update a saved opportunity
   */
  updateSaved: async (savedId: string, data: SavedOpportunityUpdate): Promise<SavedOpportunity> => {
    const response = await apiClient.patch(`/opportunities/saved/${savedId}`, data);
    return response.data;
  },

  /**
   * Remove saved opportunity
   */
  unsave: async (savedId: string): Promise<void> => {
    await apiClient.delete(`/opportunities/saved/${savedId}`);
  },

  /**
   * Get pipeline statistics
   */
  getPipelineStats: async (): Promise<PipelineStats> => {
    const response = await apiClient.get('/opportunities/saved/stats');
    return response.data;
  },

  /**
   * Get personalized scores for opportunities
   */
  getScores: async (params?: {
    opportunity_ids?: string[];
    page?: number;
    page_size?: number;
  }): Promise<{
    items: OpportunityScore[];
    total: number;
    page: number;
    page_size: number;
  }> => {
    const response = await apiClient.get('/opportunities/scores', { params });
    return response.data;
  },

  /**
   * Get personalized score for a single opportunity
   */
  getScore: async (opportunityId: string): Promise<OpportunityScore | { has_score: false; message: string }> => {
    const response = await apiClient.get(`/opportunities/scores/${opportunityId}`);
    return response.data;
  },
};

// Types for scoring
export interface OpportunityScore {
  opportunity_id: string;
  has_score?: boolean;
  overall_score: number;
  capability_score: number;
  capability_breakdown: Record<string, unknown>;
  eligibility_score: number;
  eligibility_breakdown: Record<string, unknown>;
  scale_score: number;
  scale_breakdown: Record<string, unknown>;
  clearance_score: number;
  clearance_breakdown: Record<string, unknown>;
  contract_type_score: number;
  contract_type_breakdown: Record<string, unknown>;
  timeline_score: number;
  timeline_breakdown: Record<string, unknown>;
  is_stale?: boolean;
  stale_reason?: string;
  calculated_at?: string;
}

// Win Probability types
export interface WinProbabilityFactor {
  name: string;
  impact: number;
  detail: string;
}

export interface WinProbability {
  probability: number;
  confidence: 'low' | 'medium' | 'high';
  factors: WinProbabilityFactor[];
  recommendation: string;
  algorithm_version?: string;
  calculated_at?: string;
}

// Incumbent Vulnerability types
export interface VulnerabilityFactor {
  score: number;
  weight: number;
  detail: string;
}

export interface IncumbentVulnerability {
  incumbent_name: string | null;
  incumbent_uei: string;
  vulnerability_score: number;
  level: 'Low' | 'Medium' | 'High';
  factors: {
    concentration: VulnerabilityFactor;
    expertise: VulnerabilityFactor;
    trajectory: VulnerabilityFactor;
    market_share: VulnerabilityFactor;
    recompete_history: VulnerabilityFactor;
  };
  recommendation: string;
  summary?: {
    total_contracts: number;
    total_value: number;
  };
  algorithm_version?: string;
  calculated_at?: string;
}

// Win Probability API
export const getWinProbability = async (opportunityId: string): Promise<WinProbability> => {
  const response = await apiClient.get(`/opportunities/${opportunityId}/win-probability`);
  return response.data;
};

// Incumbent Vulnerability API (public, no auth required)
export const getIncumbentVulnerability = async (
  uei: string,
  naicsCode?: string,
  agencyName?: string
): Promise<IncumbentVulnerability> => {
  const params: Record<string, string> = {};
  if (naicsCode) params.naics_code = naicsCode;
  if (agencyName) params.agency_name = agencyName;
  const response = await apiClient.get(`/analytics/competitors/incumbent/${uei}/vulnerability`, { params });
  return response.data;
};

export default opportunitiesApi;
