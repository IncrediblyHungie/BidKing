/**
 * Authentication Store - Zustand with Supabase
 *
 * Manages user authentication state using Supabase Auth
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User as SupabaseUser, Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';

interface User {
  id: string;
  email: string;
  company_name?: string;
  subscription_tier: string;
  is_verified: boolean;
  created_at: string;
}

interface UserLogin {
  email: string;
  password: string;
}

interface UserRegister {
  email: string;
  password: string;
  company_name?: string;
}

interface AuthState {
  user: User | null;
  supabaseUser: SupabaseUser | null;
  session: Session | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (credentials: UserLogin) => Promise<void>;
  register: (data: UserRegister) => Promise<void>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  clearError: () => void;
  setSession: (session: Session | null) => void;
  initialize: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      supabaseUser: null,
      session: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      initialize: async () => {
        try {
          // Get the current session from Supabase
          const { data: { session }, error } = await supabase.auth.getSession();

          if (error) {
            console.error('Error getting session:', error);
            return;
          }

          if (session) {
            set({
              session,
              supabaseUser: session.user,
              isAuthenticated: true,
              user: {
                id: session.user.id,
                email: session.user.email || '',
                company_name: session.user.user_metadata?.company_name,
                subscription_tier: 'free',
                is_verified: session.user.email_confirmed_at != null,
                created_at: session.user.created_at,
              },
            });
          }

          // Listen for auth state changes
          supabase.auth.onAuthStateChange((_event, session) => {
            if (session) {
              set({
                session,
                supabaseUser: session.user,
                isAuthenticated: true,
                user: {
                  id: session.user.id,
                  email: session.user.email || '',
                  company_name: session.user.user_metadata?.company_name,
                  subscription_tier: 'free',
                  is_verified: session.user.email_confirmed_at != null,
                  created_at: session.user.created_at,
                },
              });
            } else {
              set({
                session: null,
                supabaseUser: null,
                user: null,
                isAuthenticated: false,
              });
            }
          });
        } catch (error) {
          console.error('Error initializing auth:', error);
        }
      },

      login: async (credentials: UserLogin) => {
        set({ isLoading: true, error: null });
        try {
          const { data, error } = await supabase.auth.signInWithPassword({
            email: credentials.email,
            password: credentials.password,
          });

          if (error) {
            throw error;
          }

          if (data.session) {
            set({
              session: data.session,
              supabaseUser: data.user,
              isAuthenticated: true,
              isLoading: false,
              user: {
                id: data.user.id,
                email: data.user.email || '',
                company_name: data.user.user_metadata?.company_name,
                subscription_tier: 'free',
                is_verified: data.user.email_confirmed_at != null,
                created_at: data.user.created_at,
              },
            });
          }
        } catch (error: any) {
          set({
            isLoading: false,
            error: error.message || 'Login failed',
          });
          throw error;
        }
      },

      register: async (data: UserRegister) => {
        set({ isLoading: true, error: null });
        try {
          const { data: authData, error } = await supabase.auth.signUp({
            email: data.email,
            password: data.password,
            options: {
              data: {
                company_name: data.company_name,
              },
            },
          });

          if (error) {
            throw error;
          }

          // If email confirmation is disabled, user is immediately logged in
          if (authData.session) {
            set({
              session: authData.session,
              supabaseUser: authData.user,
              isAuthenticated: true,
              user: {
                id: authData.user!.id,
                email: authData.user!.email || '',
                company_name: data.company_name,
                subscription_tier: 'free',
                is_verified: authData.user!.email_confirmed_at != null,
                created_at: authData.user!.created_at,
              },
            });
          }

          set({ isLoading: false });
        } catch (error: any) {
          set({
            isLoading: false,
            error: error.message || 'Registration failed',
          });
          throw error;
        }
      },

      logout: async () => {
        try {
          await supabase.auth.signOut();
          set({
            user: null,
            supabaseUser: null,
            session: null,
            isAuthenticated: false,
            error: null,
          });
        } catch (error: any) {
          console.error('Logout error:', error);
        }
      },

      fetchUser: async () => {
        try {
          const { data: { user }, error } = await supabase.auth.getUser();

          if (error) {
            throw error;
          }

          if (user) {
            set({
              supabaseUser: user,
              isAuthenticated: true,
              user: {
                id: user.id,
                email: user.email || '',
                company_name: user.user_metadata?.company_name,
                subscription_tier: 'free',
                is_verified: user.email_confirmed_at != null,
                created_at: user.created_at,
              },
            });
          } else {
            get().logout();
          }
        } catch (error) {
          get().logout();
        }
      },

      clearError: () => set({ error: null }),

      setSession: (session: Session | null) => {
        if (session) {
          set({
            session,
            supabaseUser: session.user,
            isAuthenticated: true,
            user: {
              id: session.user.id,
              email: session.user.email || '',
              company_name: session.user.user_metadata?.company_name,
              subscription_tier: 'free',
              is_verified: session.user.email_confirmed_at != null,
              created_at: session.user.created_at,
            },
          });
        } else {
          set({
            session: null,
            supabaseUser: null,
            user: null,
            isAuthenticated: false,
          });
        }
      },
    }),
    {
      name: 'bidking-auth',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

export default useAuthStore;
