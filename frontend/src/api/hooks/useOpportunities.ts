/**
 * React Query hooks for Opportunities API
 * These hooks provide automatic caching, deduplication, and background refetching
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { opportunitiesApi, OpportunityScore } from "../opportunities";
import {
  Opportunity,
  OpportunityListResponse,
  OpportunitySearchParams,
  OpportunityStats,
  SavedOpportunity,
  SavedOpportunityUpdate,
  PipelineStats,
} from "../../types";

// Query key factory for consistent cache management
export const opportunityKeys = {
  all: ["opportunities"] as const,
  lists: () => [...opportunityKeys.all, "list"] as const,
  list: (params: OpportunitySearchParams) => [...opportunityKeys.lists(), params] as const,
  details: () => [...opportunityKeys.all, "detail"] as const,
  detail: (id: string) => [...opportunityKeys.details(), id] as const,
  stats: () => [...opportunityKeys.all, "stats"] as const,
  saved: () => [...opportunityKeys.all, "saved"] as const,
  savedList: (statusFilter?: string) => [...opportunityKeys.saved(), { statusFilter }] as const,
  pipelineStats: () => [...opportunityKeys.all, "pipelineStats"] as const,
  scores: () => [...opportunityKeys.all, "scores"] as const,
  score: (id: string) => [...opportunityKeys.scores(), id] as const,
  analysis: (id: string) => [...opportunityKeys.all, "analysis", id] as const,
};

/**
 * Hook for fetching paginated opportunity list with filters
 * - Caches results for 5 minutes (staleTime from global config)
 * - Automatically deduplicates requests with same params
 */
export function useOpportunities(params: OpportunitySearchParams = {}) {
  return useQuery<OpportunityListResponse>({
    queryKey: opportunityKeys.list(params),
    queryFn: () => opportunitiesApi.list(params),
    // Keep previous data while fetching new page (smooth pagination)
    placeholderData: (previousData) => previousData,
  });
}

/**
 * Hook for fetching a single opportunity by ID
 * - Caches for 10 minutes (opportunities don't change often)
 */
export function useOpportunity(id: string, enabled = true) {
  return useQuery<Opportunity>({
    queryKey: opportunityKeys.detail(id),
    queryFn: () => opportunitiesApi.get(id),
    enabled: enabled && !!id,
    staleTime: 10 * 60 * 1000, // 10 minutes for detail pages
  });
}

/**
 * Hook for opportunity statistics (dashboard)
 * - Caches for 15 minutes (stats are aggregated, don't change quickly)
 */
export function useOpportunityStats() {
  return useQuery<OpportunityStats>({
    queryKey: opportunityKeys.stats(),
    queryFn: () => opportunitiesApi.getStats(),
    staleTime: 15 * 60 * 1000, // 15 minutes
  });
}

/**
 * Hook for opportunity analysis (score breakdown)
 */
export function useOpportunityAnalysis(id: string, enabled = true) {
  return useQuery({
    queryKey: opportunityKeys.analysis(id),
    queryFn: () => opportunitiesApi.getAnalysis(id),
    enabled: enabled && !!id,
    staleTime: 10 * 60 * 1000,
  });
}

/**
 * Hook for saved opportunities list (pipeline)
 * - Shorter cache since users actively update these
 */
export function useSavedOpportunities(statusFilter?: string) {
  return useQuery<SavedOpportunity[]>({
    queryKey: opportunityKeys.savedList(statusFilter),
    queryFn: () => opportunitiesApi.listSaved(statusFilter),
    staleTime: 2 * 60 * 1000, // 2 minutes - users update pipeline frequently
  });
}

/**
 * Hook for pipeline statistics
 */
export function usePipelineStats() {
  return useQuery<PipelineStats>({
    queryKey: opportunityKeys.pipelineStats(),
    queryFn: () => opportunitiesApi.getPipelineStats(),
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * Hook for personalized scores
 * - Fetches scores for a list of opportunity IDs
 */
export function useOpportunityScores(opportunityIds: string[], enabled = true) {
  return useQuery({
    queryKey: [...opportunityKeys.scores(), opportunityIds],
    queryFn: () => opportunitiesApi.getScores({ opportunity_ids: opportunityIds, page_size: 100 }),
    enabled: enabled && opportunityIds.length > 0,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook for single opportunity score
 */
export function useOpportunityScore(opportunityId: string, enabled = true) {
  return useQuery<OpportunityScore | { has_score: false; message: string }>({
    queryKey: opportunityKeys.score(opportunityId),
    queryFn: () => opportunitiesApi.getScore(opportunityId),
    enabled: enabled && !!opportunityId,
    staleTime: 5 * 60 * 1000,
  });
}

// ============ MUTATIONS ============

/**
 * Hook for saving an opportunity to pipeline
 */
export function useSaveOpportunity() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      opportunity_id: string;
      notes?: string;
      status?: string;
      priority?: number;
    }) => opportunitiesApi.save(data),
    onSuccess: () => {
      // Invalidate saved opportunities list to refetch
      queryClient.invalidateQueries({ queryKey: opportunityKeys.saved() });
      queryClient.invalidateQueries({ queryKey: opportunityKeys.pipelineStats() });
    },
  });
}

/**
 * Hook for updating a saved opportunity
 */
export function useUpdateSavedOpportunity() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ savedId, data }: { savedId: string; data: SavedOpportunityUpdate }) =>
      opportunitiesApi.updateSaved(savedId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: opportunityKeys.saved() });
      queryClient.invalidateQueries({ queryKey: opportunityKeys.pipelineStats() });
    },
  });
}

/**
 * Hook for removing a saved opportunity
 */
export function useUnsaveOpportunity() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (savedId: string) => opportunitiesApi.unsave(savedId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: opportunityKeys.saved() });
      queryClient.invalidateQueries({ queryKey: opportunityKeys.pipelineStats() });
    },
  });
}
