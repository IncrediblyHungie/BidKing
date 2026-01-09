/**
 * Authentication API calls
 */

import apiClient from './client';
import { User, UserLogin, UserRegister, AuthTokens } from '../types';

export const authApi = {
  /**
   * Register a new user
   */
  register: async (data: UserRegister): Promise<User> => {
    const response = await apiClient.post('/auth/register', data);
    return response.data;
  },

  /**
   * Login and get tokens
   */
  login: async (data: UserLogin): Promise<AuthTokens> => {
    const response = await apiClient.post('/auth/login', data);
    return response.data;
  },

  /**
   * Refresh access token
   */
  refresh: async (refreshToken: string): Promise<AuthTokens> => {
    const response = await apiClient.post('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return response.data;
  },

  /**
   * Verify email with token
   */
  verifyEmail: async (token: string): Promise<{ message: string }> => {
    const response = await apiClient.post(`/auth/verify-email?token=${token}`);
    return response.data;
  },

  /**
   * Request password reset
   */
  requestPasswordReset: async (email: string): Promise<{ message: string }> => {
    const response = await apiClient.post('/auth/password-reset/request', { email });
    return response.data;
  },

  /**
   * Confirm password reset
   */
  confirmPasswordReset: async (token: string, newPassword: string): Promise<{ message: string }> => {
    const response = await apiClient.post('/auth/password-reset/confirm', {
      token,
      new_password: newPassword,
    });
    return response.data;
  },

  /**
   * Get current user info
   */
  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },
};

export default authApi;
