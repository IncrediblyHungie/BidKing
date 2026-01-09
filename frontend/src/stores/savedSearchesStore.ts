/**
 * Saved Searches Store - Zustand
 *
 * Manages saved search state and CRUD operations
 */

import { create } from 'zustand';
import { SavedSearch, SavedSearchCreate, SavedSearchUpdate } from '../types';
import * as savedSearchesApi from '../api/savedSearches';

interface SavedSearchesState {
  savedSearches: SavedSearch[];
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchSavedSearches: () => Promise<void>;
  createSavedSearch: (data: SavedSearchCreate) => Promise<SavedSearch>;
  updateSavedSearch: (id: string, data: SavedSearchUpdate) => Promise<void>;
  deleteSavedSearch: (id: string) => Promise<void>;
  useSavedSearch: (id: string) => Promise<SavedSearch>;
  setDefaultSearch: (id: string) => Promise<void>;
  getDefaultFilters: () => Promise<Record<string, unknown> | null>;
  clearError: () => void;
}

export const useSavedSearchesStore = create<SavedSearchesState>()((set) => ({
  savedSearches: [],
  isLoading: false,
  error: null,

  fetchSavedSearches: async () => {
    set({ isLoading: true, error: null });
    try {
      const searches = await savedSearchesApi.listSavedSearches();
      set({ savedSearches: searches, isLoading: false });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to fetch saved searches',
      });
    }
  },

  createSavedSearch: async (data: SavedSearchCreate) => {
    set({ isLoading: true, error: null });
    try {
      const search = await savedSearchesApi.createSavedSearch(data);
      set((state) => ({
        savedSearches: [...state.savedSearches, search],
        isLoading: false,
      }));
      return search;
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to create saved search',
      });
      throw error;
    }
  },

  updateSavedSearch: async (id: string, data: SavedSearchUpdate) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await savedSearchesApi.updateSavedSearch(id, data);
      set((state) => ({
        savedSearches: state.savedSearches.map((s) => (s.id === id ? updated : s)),
        isLoading: false,
      }));
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to update saved search',
      });
      throw error;
    }
  },

  deleteSavedSearch: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      await savedSearchesApi.deleteSavedSearch(id);
      set((state) => ({
        savedSearches: state.savedSearches.filter((s) => s.id !== id),
        isLoading: false,
      }));
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to delete saved search',
      });
      throw error;
    }
  },

  useSavedSearch: async (id: string) => {
    try {
      const search = await savedSearchesApi.useSavedSearch(id);
      // Update the search in state with incremented use count
      set((state) => ({
        savedSearches: state.savedSearches.map((s) => (s.id === id ? search : s)),
      }));
      return search;
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || 'Failed to use saved search',
      });
      throw error;
    }
  },

  setDefaultSearch: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      await savedSearchesApi.setDefaultSearch(id);
      // Update all searches: unset old default, set new default
      set((state) => ({
        savedSearches: state.savedSearches.map((s) => ({
          ...s,
          is_default: s.id === id ? true : false,
        })),
        isLoading: false,
      }));
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to set default search',
      });
      throw error;
    }
  },

  getDefaultFilters: async () => {
    try {
      return await savedSearchesApi.getDefaultSearchFilters();
    } catch (error: any) {
      // Silently fail - default filters are optional
      console.debug('Could not fetch default filters:', error);
      return null;
    }
  },

  clearError: () => set({ error: null }),
}));

export default useSavedSearchesStore;
