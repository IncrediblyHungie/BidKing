/**
 * Authentication Store - Zustand
 *
 * Manages user authentication state and tokens
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, AuthTokens, UserLogin, UserRegister } from '../types';
import { authApi } from '../api';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (credentials: UserLogin) => Promise<void>;
  register: (data: UserRegister) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
  clearError: () => void;
  setTokens: (tokens: AuthTokens) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (credentials: UserLogin) => {
        set({ isLoading: true, error: null });
        try {
          const tokens = await authApi.login(credentials);

          // Store tokens
          localStorage.setItem('access_token', tokens.access_token);
          localStorage.setItem('refresh_token', tokens.refresh_token);

          set({
            accessToken: tokens.access_token,
            refreshToken: tokens.refresh_token,
            isAuthenticated: true,
            isLoading: false,
          });

          // Fetch user info
          await get().fetchUser();
        } catch (error: any) {
          set({
            isLoading: false,
            error: error.response?.data?.detail || 'Login failed',
          });
          throw error;
        }
      },

      register: async (data: UserRegister) => {
        set({ isLoading: true, error: null });
        try {
          await authApi.register(data);
          set({ isLoading: false });
          // User needs to login after registration
        } catch (error: any) {
          set({
            isLoading: false,
            error: error.response?.data?.detail || 'Registration failed',
          });
          throw error;
        }
      },

      logout: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
          error: null,
        });
      },

      fetchUser: async () => {
        try {
          const user = await authApi.getCurrentUser();
          set({ user, isAuthenticated: true });
        } catch (error) {
          // If fetching user fails, logout
          get().logout();
        }
      },

      clearError: () => set({ error: null }),

      setTokens: (tokens: AuthTokens) => {
        localStorage.setItem('access_token', tokens.access_token);
        localStorage.setItem('refresh_token', tokens.refresh_token);
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          isAuthenticated: true,
        });
      },
    }),
    {
      name: 'bidking-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

export default useAuthStore;
