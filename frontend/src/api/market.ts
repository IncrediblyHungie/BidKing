/**
 * Market Intelligence API calls
 */

import apiClient from './client';
import { NAICSStatistics, LaborRate, Recompete, MarketOverview } from '../types';

export const marketApi = {
  /**
   * Get market overview dashboard data
   */
  getOverview: async (): Promise<MarketOverview> => {
    const response = await apiClient.get('/market/overview');
    return response.data;
  },

  /**
   * Get NAICS statistics
   */
  getNAICSStats: async (naicsCode: string): Promise<NAICSStatistics> => {
    const response = await apiClient.get(`/market/naics/${naicsCode}`);
    return response.data;
  },

  /**
   * List NAICS statistics
   */
  listNAICSStats: async (limit: number = 20): Promise<NAICSStatistics[]> => {
    const response = await apiClient.get('/market/naics', { params: { limit } });
    return response.data;
  },

  /**
   * Get labor rates
   */
  getLaborRates: async (data: {
    job_title: string;
    experience_min?: number;
    experience_max?: number;
    education_level?: string;
  }): Promise<LaborRate> => {
    const response = await apiClient.post('/market/labor-rates', data);
    return response.data;
  },

  /**
   * List recompete opportunities
   */
  listRecompetes: async (params: {
    naics_code?: string;
    days_ahead?: number;
    page?: number;
    page_size?: number;
  } = {}): Promise<{
    items: Recompete[];
    total: number;
    page: number;
    page_size: number;
  }> => {
    const response = await apiClient.get('/market/recompetes', { params });
    return response.data;
  },

  /**
   * Get recompete by ID
   */
  getRecompete: async (id: string): Promise<Recompete> => {
    const response = await apiClient.get(`/market/recompetes/${id}`);
    return response.data;
  },

  /**
   * Search competitors
   */
  searchCompetitors: async (params: {
    name?: string;
    state?: string;
    naics_code?: string;
    small_business?: boolean;
    limit?: number;
  } = {}): Promise<any[]> => {
    const response = await apiClient.get('/market/competitors', { params });
    return response.data;
  },

  /**
   * Get competitor by UEI
   */
  getCompetitor: async (uei: string): Promise<any> => {
    const response = await apiClient.get(`/market/competitors/${uei}`);
    return response.data;
  },
};

export default marketApi;
