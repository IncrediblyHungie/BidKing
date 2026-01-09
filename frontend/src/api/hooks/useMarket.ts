/**
 * React Query hooks for Market Intelligence API
 * These endpoints are read-heavy and cache well
 */

import { useQuery } from "@tanstack/react-query";
import { marketApi } from "../market";
import { NAICSStatistics, Recompete, MarketOverview } from "../../types";

// Query key factory
export const marketKeys = {
  all: ["market"] as const,
  overview: () => [...marketKeys.all, "overview"] as const,
  naics: () => [...marketKeys.all, "naics"] as const,
  naicsList: (limit: number) => [...marketKeys.naics(), "list", { limit }] as const,
  naicsDetail: (code: string) => [...marketKeys.naics(), code] as const,
  recompetes: () => [...marketKeys.all, "recompetes"] as const,
  recompetesList: (params: Record<string, unknown>) => [...marketKeys.recompetes(), "list", params] as const,
  recompeteDetail: (id: string) => [...marketKeys.recompetes(), id] as const,
  competitors: () => [...marketKeys.all, "competitors"] as const,
  competitorsList: (params: Record<string, unknown>) => [...marketKeys.competitors(), "list", params] as const,
  competitorDetail: (uei: string) => [...marketKeys.competitors(), uei] as const,
};

/**
 * Hook for market overview dashboard
 * - Caches for 15 minutes (aggregated data, doesn't change quickly)
 */
export function useMarketOverview() {
  return useQuery<MarketOverview>({
    queryKey: marketKeys.overview(),
    queryFn: () => marketApi.getOverview(),
    staleTime: 15 * 60 * 1000, // 15 minutes
  });
}

/**
 * Hook for NAICS statistics list
 * - Caches for 30 minutes (rarely changes)
 */
export function useNAICSStatsList(limit: number = 20) {
  return useQuery<NAICSStatistics[]>({
    queryKey: marketKeys.naicsList(limit),
    queryFn: () => marketApi.listNAICSStats(limit),
    staleTime: 30 * 60 * 1000, // 30 minutes
  });
}

/**
 * Hook for single NAICS code statistics
 */
export function useNAICSStats(naicsCode: string, enabled = true) {
  return useQuery<NAICSStatistics>({
    queryKey: marketKeys.naicsDetail(naicsCode),
    queryFn: () => marketApi.getNAICSStats(naicsCode),
    enabled: enabled && !!naicsCode,
    staleTime: 30 * 60 * 1000,
  });
}

/**
 * Hook for recompetes list (from market API)
 */
export function useMarketRecompetes(params: {
  naics_code?: string;
  days_ahead?: number;
  page?: number;
  page_size?: number;
} = {}) {
  return useQuery({
    queryKey: marketKeys.recompetesList(params),
    queryFn: () => marketApi.listRecompetes(params),
    placeholderData: (previousData) => previousData,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

/**
 * Hook for single recompete detail
 */
export function useMarketRecompete(id: string, enabled = true) {
  return useQuery<Recompete>({
    queryKey: marketKeys.recompeteDetail(id),
    queryFn: () => marketApi.getRecompete(id),
    enabled: enabled && !!id,
    staleTime: 10 * 60 * 1000,
  });
}

/**
 * Hook for competitor search
 */
export function useCompetitorSearch(params: {
  name?: string;
  state?: string;
  naics_code?: string;
  small_business?: boolean;
  limit?: number;
} = {}, enabled = true) {
  return useQuery({
    queryKey: marketKeys.competitorsList(params),
    queryFn: () => marketApi.searchCompetitors(params),
    enabled,
    staleTime: 15 * 60 * 1000,
  });
}

/**
 * Hook for competitor detail by UEI
 */
export function useCompetitor(uei: string, enabled = true) {
  return useQuery({
    queryKey: marketKeys.competitorDetail(uei),
    queryFn: () => marketApi.getCompetitor(uei),
    enabled: enabled && !!uei,
    staleTime: 30 * 60 * 1000, // 30 minutes - company data rarely changes
  });
}
