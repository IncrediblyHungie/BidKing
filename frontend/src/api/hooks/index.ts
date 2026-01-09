/**
 * React Query hooks index
 *
 * Usage:
 *   import { useOpportunities, useMarketOverview, useAlertProfiles } from '../api/hooks';
 *
 * Benefits:
 *   - Automatic caching (5-30 min depending on data type)
 *   - Request deduplication (same params = same request)
 *   - Background refetching when data becomes stale
 *   - Automatic retries on failure
 *   - Optimistic updates for mutations
 */

// Opportunities hooks
export {
  opportunityKeys,
  useOpportunities,
  useOpportunity,
  useOpportunityStats,
  useOpportunityAnalysis,
  useSavedOpportunities,
  usePipelineStats,
  useOpportunityScores,
  useOpportunityScore,
  useSaveOpportunity,
  useUpdateSavedOpportunity,
  useUnsaveOpportunity,
} from './useOpportunities';

// Market intelligence hooks
export {
  marketKeys,
  useMarketOverview,
  useNAICSStatsList,
  useNAICSStats,
  useMarketRecompetes,
  useMarketRecompete,
  useCompetitorSearch,
  useCompetitor,
} from './useMarket';

// Alert profiles hooks
export {
  alertKeys,
  useAlertProfiles,
  useAlertProfile,
  useCreateAlertProfile,
  useUpdateAlertProfile,
  useDeleteAlertProfile,
  useTestAlertProfile,
} from './useAlerts';
