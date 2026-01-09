/**
 * Opportunities Store - Zustand
 *
 * Manages opportunities state, search, and filtering
 */

import { create } from 'zustand';
import { Opportunity, OpportunityFilters, SavedOpportunity } from '../types';
import { opportunitiesApi } from '../api';

interface OpportunitiesState {
  opportunities: Opportunity[];
  selectedOpportunity: Opportunity | null;
  savedOpportunities: SavedOpportunity[];
  isLoading: boolean;
  error: string | null;

  // Pagination
  page: number;
  pageSize: number;
  total: number;

  // Filters
  filters: OpportunityFilters;

  // Actions
  fetchOpportunities: (filters?: OpportunityFilters) => Promise<void>;
  fetchOpportunity: (id: string) => Promise<void>;
  fetchSavedOpportunities: () => Promise<void>;
  saveOpportunity: (id: string, notes?: string) => Promise<void>;
  unsaveOpportunity: (id: string) => Promise<void>;
  setFilters: (filters: Partial<OpportunityFilters>) => void;
  setPage: (page: number) => void;
  clearFilters: () => void;
  clearError: () => void;
}

const defaultFilters: OpportunityFilters = {
  keywords: '',
  naics_codes: [],
  set_aside: undefined,
  state: undefined,
  posted_from: undefined,
  posted_to: undefined,
  response_deadline_from: undefined,
  response_deadline_to: undefined,
  min_score: undefined,
  status: 'active',
  sort_by: 'response_deadline',
  sort_order: 'asc',
};

export const useOpportunitiesStore = create<OpportunitiesState>()((set, get) => ({
  opportunities: [],
  selectedOpportunity: null,
  savedOpportunities: [],
  isLoading: false,
  error: null,
  page: 1,
  pageSize: 20,
  total: 0,
  filters: { ...defaultFilters },

  fetchOpportunities: async (filters?: OpportunityFilters) => {
    set({ isLoading: true, error: null });
    try {
      const currentFilters = filters || get().filters;
      // Map OpportunityFilters to OpportunitySearchParams (API format)
      const response = await opportunitiesApi.list({
        query: currentFilters.keywords || undefined,
        naics_codes: currentFilters.naics_codes?.length ? currentFilters.naics_codes : undefined,
        states: currentFilters.state ? [currentFilters.state] : undefined,
        set_aside_types: currentFilters.set_aside ? [currentFilters.set_aside] : undefined,
        min_score: currentFilters.min_score,
        page: get().page,
        page_size: get().pageSize,
        sort_by: currentFilters.sort_by,
        sort_order: currentFilters.sort_order,
      });
      set({
        opportunities: response.items,
        total: response.total,
        isLoading: false,
      });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to fetch opportunities',
      });
    }
  },

  fetchOpportunity: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const opportunity = await opportunitiesApi.get(id);
      set({ selectedOpportunity: opportunity, isLoading: false });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to fetch opportunity',
      });
    }
  },

  fetchSavedOpportunities: async () => {
    set({ isLoading: true, error: null });
    try {
      const saved = await opportunitiesApi.listSaved();
      set({ savedOpportunities: saved, isLoading: false });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to fetch saved opportunities',
      });
    }
  },

  saveOpportunity: async (id: string, notes?: string) => {
    try {
      await opportunitiesApi.save({ opportunity_id: id, notes });
      // Refresh saved list
      await get().fetchSavedOpportunities();
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || 'Failed to save opportunity',
      });
    }
  },

  unsaveOpportunity: async (savedId: string) => {
    try {
      await opportunitiesApi.unsave(savedId);
      // Remove from local state
      set((state) => ({
        savedOpportunities: state.savedOpportunities.filter(
          (saved) => saved.id !== savedId
        ),
      }));
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || 'Failed to unsave opportunity',
      });
    }
  },

  setFilters: (filters: Partial<OpportunityFilters>) => {
    set((state) => ({
      filters: { ...state.filters, ...filters },
      page: 1, // Reset to first page on filter change
    }));
  },

  setPage: (page: number) => {
    set({ page });
  },

  clearFilters: () => {
    set({ filters: { ...defaultFilters }, page: 1 });
  },

  clearError: () => set({ error: null }),
}));

export default useOpportunitiesStore;
