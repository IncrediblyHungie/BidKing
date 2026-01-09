/**
 * Saved Searches API client
 */

import apiClient from './client';
import type { SavedSearch, SavedSearchCreate, SavedSearchUpdate } from '../types';

const BASE_URL = '/saved-searches';

/**
 * List all saved searches for current user
 */
export const listSavedSearches = async (): Promise<SavedSearch[]> => {
  const response = await apiClient.get<SavedSearch[]>(BASE_URL);
  return response.data;
};

/**
 * Create a new saved search
 */
export const createSavedSearch = async (data: SavedSearchCreate): Promise<SavedSearch> => {
  const response = await apiClient.post<SavedSearch>(BASE_URL, data);
  return response.data;
};

/**
 * Get a specific saved search
 */
export const getSavedSearch = async (id: string): Promise<SavedSearch> => {
  const response = await apiClient.get<SavedSearch>(`${BASE_URL}/${id}`);
  return response.data;
};

/**
 * Update a saved search
 */
export const updateSavedSearch = async (id: string, data: SavedSearchUpdate): Promise<SavedSearch> => {
  const response = await apiClient.patch<SavedSearch>(`${BASE_URL}/${id}`, data);
  return response.data;
};

/**
 * Delete a saved search
 */
export const deleteSavedSearch = async (id: string): Promise<void> => {
  await apiClient.delete(`${BASE_URL}/${id}`);
};

/**
 * Mark a saved search as used (increments use count)
 */
export const useSavedSearch = async (id: string): Promise<SavedSearch> => {
  const response = await apiClient.post<SavedSearch>(`${BASE_URL}/${id}/use`);
  return response.data;
};

/**
 * Set a saved search as the default
 */
export const setDefaultSearch = async (id: string): Promise<SavedSearch> => {
  const response = await apiClient.post<SavedSearch>(`${BASE_URL}/${id}/set-default`);
  return response.data;
};

/**
 * Get the default search filters (if any)
 */
export const getDefaultSearchFilters = async (): Promise<Record<string, unknown> | null> => {
  const response = await apiClient.get<Record<string, unknown> | null>(`${BASE_URL}/default/filters`);
  return response.data;
};
