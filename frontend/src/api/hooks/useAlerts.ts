/**
 * React Query hooks for Alert Profiles API
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { alertsApi } from "../alerts";
import { AlertProfile, AlertProfileCreate } from "../../types";

// Query key factory
export const alertKeys = {
  all: ["alerts"] as const,
  lists: () => [...alertKeys.all, "list"] as const,
  list: () => [...alertKeys.lists()] as const,
  details: () => [...alertKeys.all, "detail"] as const,
  detail: (id: string) => [...alertKeys.details(), id] as const,
  tests: () => [...alertKeys.all, "test"] as const,
  test: (id: string) => [...alertKeys.tests(), id] as const,
};

/**
 * Hook for listing all alert profiles
 * - Caches for 5 minutes
 */
export function useAlertProfiles() {
  return useQuery<AlertProfile[]>({
    queryKey: alertKeys.list(),
    queryFn: () => alertsApi.list(),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook for single alert profile
 */
export function useAlertProfile(id: string, enabled = true) {
  return useQuery<AlertProfile>({
    queryKey: alertKeys.detail(id),
    queryFn: () => alertsApi.get(id),
    enabled: enabled && !!id,
    staleTime: 5 * 60 * 1000,
  });
}

// ============ MUTATIONS ============

/**
 * Hook for creating an alert profile
 */
export function useCreateAlertProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AlertProfileCreate) => alertsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: alertKeys.lists() });
    },
  });
}

/**
 * Hook for updating an alert profile
 */
export function useUpdateAlertProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<AlertProfileCreate> }) =>
      alertsApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: alertKeys.lists() });
      queryClient.invalidateQueries({ queryKey: alertKeys.detail(variables.id) });
    },
  });
}

/**
 * Hook for deleting an alert profile
 */
export function useDeleteAlertProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => alertsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: alertKeys.lists() });
    },
  });
}

/**
 * Hook for testing an alert profile (find matching opportunities)
 * This is a mutation since it's an action, but could also be a query
 */
export function useTestAlertProfile() {
  return useMutation({
    mutationFn: (id: string) => alertsApi.test(id),
  });
}
