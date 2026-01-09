/**
 * Authentication Store - Zustand with Supabase
 *
 * Manages user authentication state using Supabase Auth
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User as SupabaseUser, Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { getOnboardingStatus } from '../api/company';
import apiClient from '../api/client';

interface User {
  id: string;
  email: string;
  company_name?: string;
  subscription_tier: string;
  is_verified: boolean;
  created_at: string;
}

// Helper to fetch actual subscription tier from backend
async function fetchSubscriptionTier(): Promise<string> {
  try {
    const response = await apiClient.get('/users/me');
    return response.data?.subscription_tier || 'free';
  } catch {
    return 'free';
  }
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

type SocialProvider = 'google' | 'azure' | 'linkedin_oidc';

interface AuthState {
  user: User | null;
  supabaseUser: SupabaseUser | null;
  session: Session | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (credentials: UserLogin) => Promise<void>;
  loginWithProvider: (provider: SocialProvider) => Promise<void>;
  register: (data: UserRegister) => Promise<void>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  clearError: () => void;
  setSession: (session: Session | null) => Promise<void>;
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
          // Check if this is an OAuth callback (hash contains access_token or error)
          const isOAuthCallback = window.location.hash.includes('access_token') ||
                                   window.location.hash.includes('error') ||
                                   window.location.search.includes('code=');

          // Get the current session from Supabase
          const { data: { session }, error } = await supabase.auth.getSession();

          if (error) {
            console.error('Error getting session:', error);
            return;
          }

          if (session) {
            // Fetch actual subscription tier from backend
            const tier = await fetchSubscriptionTier();

            set({
              session,
              supabaseUser: session.user,
              isAuthenticated: true,
              user: {
                id: session.user.id,
                email: session.user.email || '',
                company_name: session.user.user_metadata?.company_name || session.user.user_metadata?.full_name,
                subscription_tier: tier,
                is_verified: session.user.email_confirmed_at != null,
                created_at: session.user.created_at,
              },
            });

            // If this is an OAuth callback, handle the redirect
            if (isOAuthCallback && window.location.pathname === '/') {
              // Clear the hash/query from URL
              window.history.replaceState(null, '', '/');
              // Small delay to ensure state is set, then redirect
              setTimeout(async () => {
                try {
                  const status = await getOnboardingStatus();
                  if (!status.onboarding_completed && status.onboarding_step !== -1) {
                    window.location.replace('/company-setup');
                  } else {
                    window.location.replace('/dashboard');
                  }
                } catch {
                  // New user, redirect to onboarding
                  window.location.replace('/company-setup');
                }
              }, 100);
              return; // Don't set up listener yet, we're redirecting
            }
          }

          // Listen for auth state changes (for non-callback scenarios)
          supabase.auth.onAuthStateChange(async (event, session) => {
            console.log('Auth state change:', event, session?.user?.email);

            if (session) {
              // Fetch actual subscription tier from backend
              const tier = await fetchSubscriptionTier();

              set({
                session,
                supabaseUser: session.user,
                isAuthenticated: true,
                user: {
                  id: session.user.id,
                  email: session.user.email || '',
                  company_name: session.user.user_metadata?.company_name || session.user.user_metadata?.full_name,
                  subscription_tier: tier,
                  is_verified: session.user.email_confirmed_at != null,
                  created_at: session.user.created_at,
                },
              });

              // On SIGNED_IN event from OAuth, redirect if on landing page
              if (event === 'SIGNED_IN' && (window.location.pathname === '/' || window.location.pathname === '/signin' || window.location.pathname === '/signup')) {
                getOnboardingStatus()
                  .then((status) => {
                    if (!status.onboarding_completed && status.onboarding_step !== -1) {
                      window.location.replace('/company-setup');
                    } else {
                      window.location.replace('/dashboard');
                    }
                  })
                  .catch(() => {
                    // New user, redirect to onboarding
                    window.location.replace('/company-setup');
                  });
              }
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
            // Fetch actual subscription tier from backend
            const tier = await fetchSubscriptionTier();

            set({
              session: data.session,
              supabaseUser: data.user,
              isAuthenticated: true,
              isLoading: false,
              user: {
                id: data.user.id,
                email: data.user.email || '',
                company_name: data.user.user_metadata?.company_name,
                subscription_tier: tier,
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

      loginWithProvider: async (provider: SocialProvider) => {
        set({ isLoading: true, error: null });
        try {
          const { error } = await supabase.auth.signInWithOAuth({
            provider,
            options: {
              // Redirect to root, auth listener will check onboarding and redirect appropriately
              redirectTo: `${window.location.origin}/`,
            },
          });

          if (error) {
            throw error;
          }
          // OAuth will redirect, so we don't need to handle success here
        } catch (error: any) {
          set({
            isLoading: false,
            error: error.message || 'Social login failed',
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
            // New users start with free tier
            set({
              session: authData.session,
              supabaseUser: authData.user,
              isAuthenticated: true,
              isLoading: false,
              user: {
                id: authData.user!.id,
                email: authData.user!.email || '',
                company_name: data.company_name,
                subscription_tier: 'free',  // New users always start free
                is_verified: authData.user!.email_confirmed_at != null,
                created_at: authData.user!.created_at,
              },
            });
            // Redirect new users to onboarding
            window.location.href = '/company-setup';
            return;
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
            // Fetch actual subscription tier from backend
            const tier = await fetchSubscriptionTier();

            set({
              supabaseUser: user,
              isAuthenticated: true,
              user: {
                id: user.id,
                email: user.email || '',
                company_name: user.user_metadata?.company_name,
                subscription_tier: tier,
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

      setSession: async (session: Session | null) => {
        if (session) {
          // Fetch actual subscription tier from backend
          const tier = await fetchSubscriptionTier();

          set({
            session,
            supabaseUser: session.user,
            isAuthenticated: true,
            user: {
              id: session.user.id,
              email: session.user.email || '',
              company_name: session.user.user_metadata?.company_name,
              subscription_tier: tier,
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
