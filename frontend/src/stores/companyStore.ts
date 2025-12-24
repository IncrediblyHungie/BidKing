/**
 * Company Store - Zustand store for company profile and scoring data
 *
 * Manages company profile, NAICS codes, certifications, and onboarding state
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  CompanyProfile,
  CompanyNAICS,
  CompanyCertification,
  PastPerformance,
  OnboardingStatus,
  CapabilityStatement,
  getCompanyProfile,
  createCompanyProfile,
  updateCompanyProfile,
  listNAICSCodes,
  addNAICSCode,
  deleteNAICSCode,
  listCertifications,
  addCertification,
  deleteCertification,
  listPastPerformance,
  addPastPerformance,
  deletePastPerformance,
  listCapabilityStatements,
  uploadCapabilityStatement as apiUploadCapabilityStatement,
  deleteCapabilityStatement as apiDeleteCapabilityStatement,
  getOnboardingStatus,
  completeOnboarding as apiCompleteOnboarding,
  skipOnboarding as apiSkipOnboarding,
  calculateScores,
  ScoreCalculationResult,
} from '../api/company';

// Key for tracking when scores were last updated
const SCORES_UPDATED_KEY = 'bidking_scores_updated';

interface CompanyState {
  // Data
  profile: CompanyProfile | null;
  naicsCodes: CompanyNAICS[];
  certifications: CompanyCertification[];
  pastPerformance: PastPerformance[];
  capabilityStatements: CapabilityStatement[];
  onboardingStatus: OnboardingStatus | null;

  // UI State
  isLoading: boolean;
  isUploading: boolean;
  error: string | null;

  // Profile Actions
  fetchProfile: () => Promise<void>;
  createProfile: (data: Partial<CompanyProfile>) => Promise<CompanyProfile>;
  updateProfile: (data: Partial<CompanyProfile>) => Promise<CompanyProfile>;

  // NAICS Actions
  fetchNAICSCodes: () => Promise<void>;
  addNAICS: (data: {
    naics_code: string;
    naics_description?: string;
    experience_level?: string;
    is_primary?: boolean;
    years_experience?: number;
    contracts_won?: number;
  }) => Promise<CompanyNAICS>;
  removeNAICS: (naicsId: string) => Promise<void>;

  // Certification Actions
  fetchCertifications: () => Promise<void>;
  addCert: (data: {
    certification_type: string;
    certification_number?: string;
    certifying_agency?: string;
    issue_date?: string;
    expiration_date?: string;
    is_active?: boolean;
  }) => Promise<CompanyCertification>;
  removeCert: (certId: string) => Promise<void>;

  // Past Performance Actions
  fetchPastPerformance: () => Promise<void>;
  addPP: (data: Partial<PastPerformance>) => Promise<PastPerformance>;
  removePP: (ppId: string) => Promise<void>;

  // Capability Statement Actions
  fetchCapabilityStatements: () => Promise<void>;
  uploadCapabilityStatement: (file: File, name?: string, isDefault?: boolean) => Promise<CapabilityStatement>;
  removeCapabilityStatement: (capId: string) => Promise<void>;

  // Onboarding Actions
  fetchOnboardingStatus: () => Promise<OnboardingStatus>;
  completeOnboarding: () => Promise<CompanyProfile>;
  skipOnboarding: () => Promise<void>;

  // Scoring Actions
  triggerScoreRefresh: () => void;
  recalculateScores: () => Promise<ScoreCalculationResult | null>;

  // Utility
  clearError: () => void;
  clearAll: () => void;
}

// Helper to mark that scores have been updated
export function markScoresUpdated(): void {
  localStorage.setItem(SCORES_UPDATED_KEY, Date.now().toString());
}

// Helper to get the last scores update timestamp
export function getScoresUpdatedTimestamp(): number {
  const timestamp = localStorage.getItem(SCORES_UPDATED_KEY);
  return timestamp ? parseInt(timestamp, 10) : 0;
}

// Helper to clear the scores updated flag
export function clearScoresUpdatedFlag(): void {
  localStorage.removeItem(SCORES_UPDATED_KEY);
}

export const useCompanyStore = create<CompanyState>()(
  persist(
    (set, get) => ({
      // Initial State
      profile: null,
      naicsCodes: [],
      certifications: [],
      pastPerformance: [],
      capabilityStatements: [],
      onboardingStatus: null,
      isLoading: false,
      isUploading: false,
      error: null,

      // =======================================================================
      // Profile Actions
      // =======================================================================

      fetchProfile: async () => {
        set({ isLoading: true, error: null });
        try {
          const profile = await getCompanyProfile();
          set({ profile, isLoading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to fetch profile',
            isLoading: false,
          });
        }
      },

      createProfile: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const profile = await createCompanyProfile(data);
          set({ profile, isLoading: false });
          return profile;
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to create profile',
            isLoading: false,
          });
          throw error;
        }
      },

      updateProfile: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const profile = await updateCompanyProfile(data);
          set({ profile, isLoading: false });
          return profile;
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to update profile',
            isLoading: false,
          });
          throw error;
        }
      },

      // =======================================================================
      // NAICS Actions
      // =======================================================================

      fetchNAICSCodes: async () => {
        set({ isLoading: true, error: null });
        try {
          const naicsCodes = await listNAICSCodes();
          set({ naicsCodes, isLoading: false });
        } catch (error: any) {
          // 404 is ok - means no profile yet
          if (error.response?.status === 404) {
            set({ naicsCodes: [], isLoading: false });
            return;
          }
          set({
            error: error.response?.data?.detail || error.message || 'Failed to fetch NAICS codes',
            isLoading: false,
          });
        }
      },

      addNAICS: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const naics = await addNAICSCode(data);
          set((state) => ({
            naicsCodes: [...state.naicsCodes, naics],
            isLoading: false,
          }));
          // Mark that scores have been updated (backend recalculates on NAICS change)
          markScoresUpdated();
          return naics;
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to add NAICS code',
            isLoading: false,
          });
          throw error;
        }
      },

      removeNAICS: async (naicsId) => {
        set({ isLoading: true, error: null });
        try {
          await deleteNAICSCode(naicsId);
          set((state) => ({
            naicsCodes: state.naicsCodes.filter((n) => n.id !== naicsId),
            isLoading: false,
          }));
          // Mark that scores have been updated (backend recalculates on NAICS change)
          markScoresUpdated();
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to remove NAICS code',
            isLoading: false,
          });
          throw error;
        }
      },

      // =======================================================================
      // Certification Actions
      // =======================================================================

      fetchCertifications: async () => {
        set({ isLoading: true, error: null });
        try {
          const certifications = await listCertifications();
          set({ certifications, isLoading: false });
        } catch (error: any) {
          if (error.response?.status === 404) {
            set({ certifications: [], isLoading: false });
            return;
          }
          set({
            error: error.response?.data?.detail || error.message || 'Failed to fetch certifications',
            isLoading: false,
          });
        }
      },

      addCert: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const cert = await addCertification(data);
          set((state) => ({
            certifications: [...state.certifications, cert],
            isLoading: false,
          }));
          // Mark that scores have been updated (backend recalculates on cert change)
          markScoresUpdated();
          return cert;
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to add certification',
            isLoading: false,
          });
          throw error;
        }
      },

      removeCert: async (certId) => {
        set({ isLoading: true, error: null });
        try {
          await deleteCertification(certId);
          set((state) => ({
            certifications: state.certifications.filter((c) => c.id !== certId),
            isLoading: false,
          }));
          // Mark that scores have been updated (backend recalculates on cert change)
          markScoresUpdated();
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to remove certification',
            isLoading: false,
          });
          throw error;
        }
      },

      // =======================================================================
      // Past Performance Actions
      // =======================================================================

      fetchPastPerformance: async () => {
        set({ isLoading: true, error: null });
        try {
          const pastPerformance = await listPastPerformance();
          set({ pastPerformance, isLoading: false });
        } catch (error: any) {
          if (error.response?.status === 404) {
            set({ pastPerformance: [], isLoading: false });
            return;
          }
          set({
            error: error.response?.data?.detail || error.message || 'Failed to fetch past performance',
            isLoading: false,
          });
        }
      },

      addPP: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const pp = await addPastPerformance(data);
          set((state) => ({
            pastPerformance: [...state.pastPerformance, pp],
            isLoading: false,
          }));
          return pp;
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to add past performance',
            isLoading: false,
          });
          throw error;
        }
      },

      removePP: async (ppId) => {
        set({ isLoading: true, error: null });
        try {
          await deletePastPerformance(ppId);
          set((state) => ({
            pastPerformance: state.pastPerformance.filter((p) => p.id !== ppId),
            isLoading: false,
          }));
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to remove past performance',
            isLoading: false,
          });
          throw error;
        }
      },

      // =======================================================================
      // Capability Statement Actions
      // =======================================================================

      fetchCapabilityStatements: async () => {
        set({ isLoading: true, error: null });
        try {
          const capabilityStatements = await listCapabilityStatements();
          set({ capabilityStatements, isLoading: false });
        } catch (error: any) {
          if (error.response?.status === 404) {
            set({ capabilityStatements: [], isLoading: false });
            return;
          }
          set({
            error: error.response?.data?.detail || error.message || 'Failed to fetch capability statements',
            isLoading: false,
          });
        }
      },

      uploadCapabilityStatement: async (file, name, isDefault = false) => {
        set({ isUploading: true, error: null });
        try {
          const capStatement = await apiUploadCapabilityStatement(file, name, isDefault);
          set((state) => ({
            capabilityStatements: [...state.capabilityStatements, capStatement],
            isUploading: false,
          }));
          // Mark that scores have been updated (backend recalculates on capability statement upload)
          markScoresUpdated();
          return capStatement;
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to upload capability statement',
            isUploading: false,
          });
          throw error;
        }
      },

      removeCapabilityStatement: async (capId) => {
        set({ isLoading: true, error: null });
        try {
          await apiDeleteCapabilityStatement(capId);
          set((state) => ({
            capabilityStatements: state.capabilityStatements.filter((c) => c.id !== capId),
            isLoading: false,
          }));
          // Mark that scores have been updated (backend recalculates on capability statement deletion)
          markScoresUpdated();
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to remove capability statement',
            isLoading: false,
          });
          throw error;
        }
      },

      // =======================================================================
      // Onboarding Actions
      // =======================================================================

      fetchOnboardingStatus: async () => {
        set({ isLoading: true, error: null });
        try {
          const status = await getOnboardingStatus();
          set({ onboardingStatus: status, isLoading: false });
          return status;
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to fetch onboarding status',
            isLoading: false,
          });
          throw error;
        }
      },

      completeOnboarding: async () => {
        set({ isLoading: true, error: null });
        try {
          const profile = await apiCompleteOnboarding();
          set({
            profile,
            onboardingStatus: {
              onboarding_completed: true,
              onboarding_step: 5,
              profile_completeness: profile.profile_completeness,
              has_profile: true,
              has_naics: get().naicsCodes.length > 0,
              has_certifications: get().certifications.length > 0,
            },
            isLoading: false,
          });
          return profile;
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to complete onboarding',
            isLoading: false,
          });
          throw error;
        }
      },

      skipOnboarding: async () => {
        set({ isLoading: true, error: null });
        try {
          await apiSkipOnboarding();
          set({
            onboardingStatus: {
              onboarding_completed: false,
              onboarding_step: -1,
              profile_completeness: 0,
              has_profile: true,
              has_naics: false,
              has_certifications: false,
            },
            isLoading: false,
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || error.message || 'Failed to skip onboarding',
            isLoading: false,
          });
          throw error;
        }
      },

      // =======================================================================
      // Scoring Actions
      // =======================================================================

      triggerScoreRefresh: () => {
        // Mark that scores have been updated
        markScoresUpdated();
      },

      recalculateScores: async () => {
        try {
          const result = await calculateScores();
          // Mark that scores have been updated
          markScoresUpdated();
          return result;
        } catch (error: any) {
          console.error('Failed to recalculate scores:', error);
          return null;
        }
      },

      // =======================================================================
      // Utility
      // =======================================================================

      clearError: () => set({ error: null }),

      clearAll: () =>
        set({
          profile: null,
          naicsCodes: [],
          certifications: [],
          pastPerformance: [],
          capabilityStatements: [],
          onboardingStatus: null,
          error: null,
        }),
    }),
    {
      name: 'bidking-company',
      partialize: (state) => ({
        profile: state.profile,
        onboardingStatus: state.onboardingStatus,
      }),
    }
  )
);

export default useCompanyStore;
