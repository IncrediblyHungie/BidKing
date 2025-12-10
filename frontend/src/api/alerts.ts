/**
 * Alert Profiles API calls
 */

import apiClient from './client';
import { AlertProfile, AlertProfileCreate } from '../types';

export const alertsApi = {
  /**
   * List all alert profiles
   */
  list: async (): Promise<AlertProfile[]> => {
    const response = await apiClient.get('/alerts');
    return response.data;
  },

  /**
   * Get alert profile by ID
   */
  get: async (id: string): Promise<AlertProfile> => {
    const response = await apiClient.get(`/alerts/${id}`);
    return response.data;
  },

  /**
   * Create new alert profile
   */
  create: async (data: AlertProfileCreate): Promise<AlertProfile> => {
    const response = await apiClient.post('/alerts', data);
    return response.data;
  },

  /**
   * Update alert profile
   */
  update: async (id: string, data: Partial<AlertProfileCreate>): Promise<AlertProfile> => {
    const response = await apiClient.patch(`/alerts/${id}`, data);
    return response.data;
  },

  /**
   * Delete alert profile
   */
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/alerts/${id}`);
  },

  /**
   * Test alert profile (find matching opportunities)
   */
  test: async (id: string): Promise<{
    profile_name: string;
    match_count: number;
    sample_matches: {
      id: string;
      title: string;
      agency: string;
      score: number;
      deadline: string | null;
    }[];
  }> => {
    const response = await apiClient.post(`/alerts/${id}/test`);
    return response.data;
  },
};

export default alertsApi;
