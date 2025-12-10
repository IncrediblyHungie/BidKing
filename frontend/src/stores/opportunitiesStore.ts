/**
 * Opportunities Store - Zustand
 *
 * Manages opportunities state, search, and filtering
 */

import { create } from 'zustand';
import { Opportunity, OpportunityFilters } from '../types';
import { opportunitiesApi } from '../api';

interface OpportunitiesState {
  opportunities: Opportunity[];
  selectedOpportunity: Opportunity | null;
  savedOpportunities: Opportunity[];
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
      const response = await opportunitiesApi.list({
        ...currentFilters,
        page: get().page,
        page_size: get().pageSize,
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
      const saved = await opportunitiesApi.getSaved();
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
      await opportunitiesApi.save(id, notes);
      // Refresh saved list
      await get().fetchSavedOpportunities();
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || 'Failed to save opportunity',
      });
    }
  },

  unsaveOpportunity: async (id: string) => {
    try {
      await opportunitiesApi.unsave(id);
      // Remove from local state
      set((state) => ({
        savedOpportunities: state.savedOpportunities.filter(
          (opp) => opp.id !== id
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
