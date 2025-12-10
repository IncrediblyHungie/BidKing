/**
 * Profile Store - Zustand with Supabase
 *
 * Manages user profile data stored in Supabase
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { supabase } from '../lib/supabase';

export interface UserProfile {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  company_name: string;
  bio: string;
  country: string;
  city: string;
  state: string;
  postal_code: string;
  profile_completed: boolean;
  created_at: string;
  updated_at: string;
}

interface ProfileState {
  profile: UserProfile | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchProfile: (userId: string) => Promise<void>;
  updateProfile: (userId: string, data: Partial<UserProfile>) => Promise<void>;
  completeOnboarding: (userId: string, data: Partial<UserProfile>) => Promise<void>;
  clearProfile: () => void;
  clearError: () => void;
}

const defaultProfile: Partial<UserProfile> = {
  first_name: '',
  last_name: '',
  phone: '',
  company_name: '',
  bio: '',
  country: '',
  city: '',
  state: '',
  postal_code: '',
  profile_completed: false,
};

export const useProfileStore = create<ProfileState>()(
  persist(
    (set) => ({
      profile: null,
      isLoading: false,
      error: null,

      fetchProfile: async (userId: string) => {
        set({ isLoading: true, error: null });
        try {
          const { data, error } = await supabase
            .from('profiles')
            .select('*')
            .eq('id', userId)
            .single();

          if (error) {
            // Profile doesn't exist yet, create one
            if (error.code === 'PGRST116') {
              const { data: userData } = await supabase.auth.getUser();
              const newProfile = {
                id: userId,
                email: userData.user?.email || '',
                ...defaultProfile,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              };

              const { data: insertedProfile, error: insertError } = await supabase
                .from('profiles')
                .insert([newProfile])
                .select()
                .single();

              if (insertError) {
                throw insertError;
              }

              set({ profile: insertedProfile as UserProfile, isLoading: false });
              return;
            }
            throw error;
          }

          set({ profile: data as UserProfile, isLoading: false });
        } catch (error: any) {
          set({ error: error.message || 'Failed to fetch profile', isLoading: false });
        }
      },

      updateProfile: async (userId: string, data: Partial<UserProfile>) => {
        set({ isLoading: true, error: null });
        try {
          const { data: updatedProfile, error } = await supabase
            .from('profiles')
            .update({
              ...data,
              updated_at: new Date().toISOString(),
            })
            .eq('id', userId)
            .select()
            .single();

          if (error) throw error;

          set({ profile: updatedProfile as UserProfile, isLoading: false });
        } catch (error: any) {
          set({ error: error.message || 'Failed to update profile', isLoading: false });
          throw error;
        }
      },

      completeOnboarding: async (userId: string, data: Partial<UserProfile>) => {
        set({ isLoading: true, error: null });
        try {
          const { data: updatedProfile, error } = await supabase
            .from('profiles')
            .upsert({
              id: userId,
              ...data,
              profile_completed: true,
              updated_at: new Date().toISOString(),
            })
            .select()
            .single();

          if (error) throw error;

          set({ profile: updatedProfile as UserProfile, isLoading: false });
        } catch (error: any) {
          set({ error: error.message || 'Failed to complete onboarding', isLoading: false });
          throw error;
        }
      },

      clearProfile: () => set({ profile: null }),
      clearError: () => set({ error: null }),
    }),
    {
      name: 'bidking-profile',
      partialize: (state) => ({
        profile: state.profile,
      }),
    }
  )
);

export default useProfileStore;
