/**
 * Alerts Store - Zustand
 *
 * Manages alert profile state and CRUD operations
 */

import { create } from 'zustand';
import { AlertProfile, AlertProfileCreate } from '../types';
import { alertsApi } from '../api';

interface AlertsState {
  alertProfiles: AlertProfile[];
  selectedProfile: AlertProfile | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchAlertProfiles: () => Promise<void>;
  fetchAlertProfile: (id: string) => Promise<void>;
  createAlertProfile: (data: AlertProfileCreate) => Promise<AlertProfile>;
  updateAlertProfile: (id: string, data: Partial<AlertProfileCreate>) => Promise<void>;
  deleteAlertProfile: (id: string) => Promise<void>;
  toggleProfileActive: (id: string) => Promise<void>;
  testAlertProfile: (id: string) => Promise<{
    profile_name: string;
    match_count: number;
    sample_matches: {
      id: string;
      title: string;
      agency: string;
      score: number;
      deadline: string | null;
    }[];
  }>;
  clearError: () => void;
}

export const useAlertsStore = create<AlertsState>()((set, get) => ({
  alertProfiles: [],
  selectedProfile: null,
  isLoading: false,
  error: null,

  fetchAlertProfiles: async () => {
    set({ isLoading: true, error: null });
    try {
      const profiles = await alertsApi.list();
      set({ alertProfiles: profiles, isLoading: false });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to fetch alert profiles',
      });
    }
  },

  fetchAlertProfile: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const profile = await alertsApi.get(id);
      set({ selectedProfile: profile, isLoading: false });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to fetch alert profile',
      });
    }
  },

  createAlertProfile: async (data: AlertProfileCreate) => {
    set({ isLoading: true, error: null });
    try {
      const profile = await alertsApi.create(data);
      set((state) => ({
        alertProfiles: [...state.alertProfiles, profile],
        isLoading: false,
      }));
      return profile;
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to create alert profile',
      });
      throw error;
    }
  },

  updateAlertProfile: async (id: string, data: Partial<AlertProfileCreate>) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await alertsApi.update(id, data);
      set((state) => ({
        alertProfiles: state.alertProfiles.map((p) => (p.id === id ? updated : p)),
        selectedProfile: state.selectedProfile?.id === id ? updated : state.selectedProfile,
        isLoading: false,
      }));
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to update alert profile',
      });
      throw error;
    }
  },

  deleteAlertProfile: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      await alertsApi.delete(id);
      set((state) => ({
        alertProfiles: state.alertProfiles.filter((p) => p.id !== id),
        selectedProfile: state.selectedProfile?.id === id ? null : state.selectedProfile,
        isLoading: false,
      }));
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.response?.data?.detail || 'Failed to delete alert profile',
      });
      throw error;
    }
  },

  toggleProfileActive: async (id: string) => {
    const profile = get().alertProfiles.find((p) => p.id === id);
    if (!profile) return;

    try {
      await get().updateAlertProfile(id, { is_active: !profile.is_active });
    } catch {
      // Error already handled in updateAlertProfile
    }
  },

  testAlertProfile: async (id: string) => {
    try {
      const result = await alertsApi.test(id);
      return result;
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || 'Failed to test alert profile',
      });
      throw error;
    }
  },

  clearError: () => set({ error: null }),
}));

export default useAlertsStore;
