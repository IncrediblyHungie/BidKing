import { useEffect, useState, useCallback, useRef } from "react";
import { Link } from "react-router";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";
import Input from "../../components/form/input/InputField";
import Label from "../../components/form/Label";
import Button from "../../components/ui/button/Button";
import SearchableSelect from "../../components/form/SearchableSelect";
import { Opportunity, SavedSearch, SavedSearchCreate } from "../../types";
import { useAuthStore } from "../../stores/authStore";
import { useSavedSearchesStore } from "../../stores/savedSearchesStore";
import { opportunitiesApi, OpportunityScore } from "../../api/opportunities";
import { getScoresUpdatedTimestamp, clearScoresUpdatedFlag } from "../../stores/companyStore";

interface FilterStats {
  total_active: number;
  new_today: number;
  score_distribution: { high: number; medium: number; low: number };
  top_agencies: { name: string; count: number }[];
  top_naics: { code: string; count: number }[];
}

// Score badge component - unified purple "Your Fit" style
function ScoreBadge({ score }: { score: number }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400">
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
      </svg>
      <span className="font-bold">{score}</span>
      <span className="text-xs opacity-75">Your Fit</span>
    </span>
  );
}

// Personalized score badge with tooltip
function PersonalizedScoreBadge({ score }: { score: OpportunityScore }) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <div className="relative">
      <div
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className="cursor-help"
      >
        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400">
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          <span className="font-bold">{score.overall_score}</span>
          <span className="text-xs opacity-75">Your Fit</span>
        </span>
      </div>

      {showTooltip && (
        <div className="absolute z-50 p-3 text-xs bg-white border rounded-lg shadow-lg dark:bg-gray-800 dark:border-gray-700 w-56 -left-20 top-8">
          <div className="font-medium mb-2 text-gray-900 dark:text-white">Score Breakdown</div>
          <div className="space-y-1.5">
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">NAICS Match</span>
              <span className="font-medium">{score.capability_score}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Set-Aside Eligibility</span>
              <span className="font-medium">{score.eligibility_score}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Scale Fit</span>
              <span className="font-medium">{score.scale_score}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Clearance</span>
              <span className="font-medium">{score.clearance_score}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Contract Type</span>
              <span className="font-medium">{score.contract_type_score}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Timeline</span>
              <span className="font-medium">{score.timeline_score}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Format date helper
function formatDate(dateString: string | null): string {
  if (!dateString) return "N/A";
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// Days until deadline
function getDaysUntil(dateString: string | null): string {
  if (!dateString) return "";
  const now = new Date();
  const deadline = new Date(dateString);
  const diffTime = deadline.getTime() - now.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return "Expired";
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  return `${diffDays} days`;
}

// Sort icon component
function SortIcon({ column, currentSort, currentOrder }: { column: string; currentSort: string; currentOrder: string }) {
  const isActive = currentSort === column;
  return (
    <span className="inline-flex flex-col ml-1">
      <svg className={`w-3 h-3 -mb-1 ${isActive && currentOrder === "asc" ? "text-blue-600 dark:text-blue-400" : "text-gray-400"}`} fill="currentColor" viewBox="0 0 20 20">
        <path d="M5 12l5-5 5 5H5z" />
      </svg>
      <svg className={`w-3 h-3 ${isActive && currentOrder === "desc" ? "text-blue-600 dark:text-blue-400" : "text-gray-400"}`} fill="currentColor" viewBox="0 0 20 20">
        <path d="M5 8l5 5 5-5H5z" />
      </svg>
    </span>
  );
}

// Sortable header component
function SortableHeader({
  column,
  label,
  currentSort,
  currentOrder,
  onSort
}: {
  column: string;
  label: string;
  currentSort: string;
  currentOrder: string;
  onSort: (column: string) => void;
}) {
  return (
    <th
      className="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 select-none"
      onClick={() => onSort(column)}
    >
      <div className="flex items-center">
        {label}
        <SortIcon column={column} currentSort={currentSort} currentOrder={currentOrder} />
      </div>
    </th>
  );
}

export default function OpportunitiesList() {
  // Auth state for personalized scoring
  const { isAuthenticated } = useAuthStore();

  // Saved searches state
  const { savedSearches, fetchSavedSearches, createSavedSearch, useSavedSearch, deleteSavedSearch } = useSavedSearchesStore();
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveSearchName, setSaveSearchName] = useState("");
  const [saveAsDefault, setSaveAsDefault] = useState(false);
  const [showSavedSearchesDropdown, setShowSavedSearchesDropdown] = useState(false);
  const savedSearchesDropdownRef = useRef<HTMLDivElement>(null);

  // Use direct fetch instead of Zustand store (same pattern as Recompetes)
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const [searchInput, setSearchInput] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [filterStats, setFilterStats] = useState<FilterStats | null>(null);
  const [naicsFilter, setNaicsFilter] = useState("");
  const [lowCompetitionMode, setLowCompetitionMode] = useState(false);
  const [agencyFilter, setAgencyFilter] = useState("");

  // Low competition / underserved NAICS codes
  const LOW_COMPETITION_NAICS = ["541611", "519190", "611430", "541910", "541618"];
  const [setAsideFilter, setSetAsideFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [minValue, setMinValue] = useState("");
  const [maxValue, setMaxValue] = useState("");
  const [hasValueEstimate, setHasValueEstimate] = useState<"all" | "yes" | "no">("all");
  const [hasAiAnalysis, setHasAiAnalysis] = useState<"all" | "yes" | "no">("all");
  const [noticeTypeFilter, setNoticeTypeFilter] = useState("");
  const [earlyStageOnly, setEarlyStageOnly] = useState(false);
  const [includeExpired, setIncludeExpired] = useState(false);

  // Personalized scores state
  const [personalizedScores, setPersonalizedScores] = useState<Record<string, OpportunityScore>>({});

  // Sort state
  const [currentSort, setCurrentSort] = useState("response_deadline");
  const [currentOrder, setCurrentOrder] = useState("asc");

  // Fetch opportunities using direct fetch (like Recompetes)
  const fetchOpportunities = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.append("page", page.toString());
      params.append("page_size", pageSize.toString());
      params.append("sort_by", currentSort);
      params.append("sort_order", currentOrder);

      if (searchInput) params.append("query", searchInput);
      // Low competition mode overrides manual NAICS filter
      // Backend expects repeated params: naics_codes=X&naics_codes=Y (not comma-separated)
      if (lowCompetitionMode) {
        LOW_COMPETITION_NAICS.forEach(code => params.append("naics_codes", code));
      } else if (naicsFilter) {
        params.append("naics_codes", naicsFilter);
      }
      if (stateFilter) params.append("states", stateFilter);
      if (setAsideFilter) params.append("set_aside_types", setAsideFilter);
      if (minValue) params.append("min_value", minValue);
      if (maxValue) params.append("max_value", maxValue);
      if (hasValueEstimate === "yes") params.append("has_value_estimate", "true");
      if (hasValueEstimate === "no") params.append("has_value_estimate", "false");
      if (hasAiAnalysis === "yes") params.append("has_ai_analysis", "true");
      if (hasAiAnalysis === "no") params.append("has_ai_analysis", "false");
      if (agencyFilter) params.append("agencies", agencyFilter);
      if (noticeTypeFilter) params.append("notice_types", noticeTypeFilter);
      if (earlyStageOnly) params.append("early_stage_only", "true");
      if (includeExpired) params.append("include_expired", "true");

      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1"}/opportunities?${params}`
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.status}`);
      }

      const data = await response.json();
      setOpportunities(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error("Error fetching opportunities:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch opportunities");
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, currentSort, currentOrder, searchInput, naicsFilter, lowCompetitionMode, stateFilter, setAsideFilter, minValue, maxValue, hasValueEstimate, hasAiAnalysis, agencyFilter, noticeTypeFilter, earlyStageOnly, includeExpired]);

  // Fetch personalized scores for authenticated users
  const fetchPersonalizedScores = useCallback(async (opportunityIds: string[]) => {
    if (!isAuthenticated || opportunityIds.length === 0) return;

    try {
      const response = await opportunitiesApi.getScores({
        opportunity_ids: opportunityIds,
        page_size: 100,
      });

      // Merge new scores with existing ones (keep scores from other pages)
      setPersonalizedScores(prev => {
        const merged = { ...prev };
        response.items.forEach((score) => {
          merged[score.opportunity_id] = score;
        });
        return merged;
      });
    } catch (err) {
      // Silently fail - personalized scores are optional
      console.debug("Could not fetch personalized scores:", err);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchOpportunities();
    fetchFilterStats();
  }, [fetchOpportunities]);

  // Fetch saved searches when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      fetchSavedSearches();
    }
  }, [isAuthenticated, fetchSavedSearches]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (savedSearchesDropdownRef.current && !savedSearchesDropdownRef.current.contains(event.target as Node)) {
        setShowSavedSearchesDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Apply saved search filters
  const applySavedSearch = async (search: SavedSearch) => {
    try {
      await useSavedSearch(search.id);
      // Apply filters from saved search
      setSearchInput(search.search_query || "");
      setNaicsFilter(search.naics_codes?.[0] || "");
      setAgencyFilter(search.agencies?.[0] || "");
      setSetAsideFilter(search.set_aside_types?.[0] || "");
      setStateFilter(search.states?.[0] || "");
      setNoticeTypeFilter(search.notice_types?.[0] || "");
      setMinValue(search.min_value?.toString() || "");
      setMaxValue(search.max_value?.toString() || "");
      setHasAiAnalysis(search.has_ai_analysis as "all" | "yes" | "no");
      setHasValueEstimate(search.has_value_estimate as "all" | "yes" | "no");
      setEarlyStageOnly(search.early_stage_only);
      setCurrentSort(search.sort_by);
      setCurrentOrder(search.sort_order);
      setPage(1);
      setShowSavedSearchesDropdown(false);
    } catch (err) {
      console.error("Failed to apply saved search:", err);
    }
  };

  // Save current search filters
  const handleSaveSearch = async () => {
    if (!saveSearchName.trim()) return;
    try {
      const searchData: SavedSearchCreate = {
        name: saveSearchName.trim(),
        is_default: saveAsDefault,
        search_query: searchInput || undefined,
        naics_codes: naicsFilter ? [naicsFilter] : undefined,
        agencies: agencyFilter ? [agencyFilter] : undefined,
        states: stateFilter ? [stateFilter] : undefined,
        set_aside_types: setAsideFilter ? [setAsideFilter] : undefined,
        notice_types: noticeTypeFilter ? [noticeTypeFilter] : undefined,
        min_value: minValue ? parseFloat(minValue) : undefined,
        max_value: maxValue ? parseFloat(maxValue) : undefined,
        has_ai_analysis: hasAiAnalysis,
        has_value_estimate: hasValueEstimate,
        early_stage_only: earlyStageOnly,
        sort_by: currentSort,
        sort_order: currentOrder,
      };
      await createSavedSearch(searchData);
      setShowSaveModal(false);
      setSaveSearchName("");
      setSaveAsDefault(false);
    } catch (err) {
      console.error("Failed to save search:", err);
    }
  };

  // Handle delete saved search
  const handleDeleteSavedSearch = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("Delete this saved search?")) {
      try {
        await deleteSavedSearch(id);
      } catch (err) {
        console.error("Failed to delete saved search:", err);
      }
    }
  };

  // Track when scores were last fetched and for which opportunity IDs
  const lastScoreFetchRef = useRef<number>(0);
  const lastFetchedIdsRef = useRef<string>("");

  // Fetch personalized scores when opportunities load or when page changes
  useEffect(() => {
    if (opportunities.length > 0 && isAuthenticated) {
      const ids = opportunities.map((opp) => opp.id);
      const idsKey = ids.join(",");
      const scoresUpdatedAt = getScoresUpdatedTimestamp();
      const needsRefresh = scoresUpdatedAt > lastScoreFetchRef.current;
      const pageChanged = idsKey !== lastFetchedIdsRef.current;

      // Fetch if: scores were updated, page changed, or first load
      if (needsRefresh || pageChanged) {
        console.log('[Scores] Fetching personalized scores for page...');
        fetchPersonalizedScores(ids);
        lastScoreFetchRef.current = Date.now();
        lastFetchedIdsRef.current = idsKey;
        if (needsRefresh) {
          clearScoresUpdatedFlag();
        }
      }
    }
  }, [opportunities, isAuthenticated, fetchPersonalizedScores]);

  // Handle column sort
  const handleColumnSort = (column: string) => {
    const newOrder = currentSort === column && currentOrder === "asc" ? "desc" : "asc";
    setCurrentSort(column);
    setCurrentOrder(newOrder);
  };

  // Get sorted opportunities - client-side sort for personalized scores when authenticated
  const getSortedOpportunities = useCallback(() => {
    // Only do client-side sorting for score column when we have personalized scores
    if (currentSort === "likelihood_score" && isAuthenticated && Object.keys(personalizedScores).length > 0) {
      const sorted = [...opportunities].sort((a, b) => {
        const scoreA = personalizedScores[a.id]?.overall_score ?? a.likelihood_score;
        const scoreB = personalizedScores[b.id]?.overall_score ?? b.likelihood_score;
        return currentOrder === "asc" ? scoreA - scoreB : scoreB - scoreA;
      });
      return sorted;
    }
    // For all other columns, rely on server-side sorting
    return opportunities;
  }, [opportunities, currentSort, currentOrder, isAuthenticated, personalizedScores]);

  const sortedOpportunities = getSortedOpportunities();

  const fetchFilterStats = async () => {
    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1"}/opportunities/stats`
      );
      if (response.ok) {
        const data = await response.json();
        setFilterStats(data);
      }
    } catch {
      // Silently fail - stats are optional
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1); // Reset to first page
    fetchOpportunities();
  };

  const handleClearAll = () => {
    setSearchInput("");
    setNaicsFilter("");
    setLowCompetitionMode(false);
    setAgencyFilter("");
    setSetAsideFilter("");
    setStateFilter("");
    setMinValue("");
    setMaxValue("");
    setHasValueEstimate("all");
    setHasAiAnalysis("all");
    setNoticeTypeFilter("");
    setEarlyStageOnly(false);
    setIncludeExpired(false);
    setPage(1);
  };

  const handleLowCompetitionToggle = () => {
    setLowCompetitionMode(!lowCompetitionMode);
    if (!lowCompetitionMode) {
      setNaicsFilter(""); // Clear manual NAICS when enabling low competition
    }
    setPage(1);
  };

  const handleExportCSV = async () => {
    try {
      const params = new URLSearchParams();
      if (searchInput) params.append("query", searchInput);
      if (naicsFilter) params.append("naics_codes", naicsFilter);
      if (stateFilter) params.append("states", stateFilter);
      if (setAsideFilter) params.append("set_aside_types", setAsideFilter);
      if (minValue) params.append("min_value", minValue);
      if (maxValue) params.append("max_value", maxValue);
      if (hasValueEstimate === "yes") params.append("has_value_estimate", "true");
      if (hasValueEstimate === "no") params.append("has_value_estimate", "false");

      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1"}/opportunities/export/csv?${params}`
      );

      if (!response.ok) throw new Error("Export failed");

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `bidking_opportunities_${new Date().toISOString().split("T")[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error("Export error:", err);
      alert("Failed to export CSV");
    }
  };

  const activeFilterCount = [
    searchInput,
    naicsFilter,
    lowCompetitionMode ? "lowComp" : "",
    agencyFilter,
    setAsideFilter,
    stateFilter,
    minValue,
    maxValue,
    hasValueEstimate !== "all" ? "hasValue" : "",
    hasAiAnalysis !== "all" ? "hasAi" : "",
    noticeTypeFilter,
    earlyStageOnly ? "earlyStage" : "",
    includeExpired ? "expired" : "",
  ].filter(Boolean).length;

  const totalPages = Math.ceil(total / pageSize);

  // Common set-aside types
  const setAsideTypes = [
    { value: "SBA", label: "Small Business" },
    { value: "SBP", label: "Small Business Set-Aside" },
    { value: "8A", label: "8(a)" },
    { value: "8AN", label: "8(a) Native American" },
    { value: "HZC", label: "HUBZone" },
    { value: "SDVOSBC", label: "Service-Disabled Veteran" },
    { value: "WOSB", label: "Women-Owned Small Business" },
    { value: "EDWOSB", label: "Economically Disadvantaged WOSB" },
  ];

  // US States
  const usStates = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
  ];

  // Notice types
  const noticeTypes = [
    { value: "Solicitation", label: "Solicitation" },
    { value: "Sources Sought", label: "Sources Sought" },
    { value: "Presolicitation", label: "Presolicitation" },
    { value: "Combined Synopsis/Solicitation", label: "Combined Synopsis/Solicitation" },
    { value: "Award Notice", label: "Award Notice" },
    { value: "Special Notice", label: "Special Notice" },
    { value: "Intent to Bundle Requirements", label: "Intent to Bundle" },
  ];

  // Sort options for dropdown
  const sortOptions = [
    { value: "posted_date", label: "Posted Date (Newest)" },
    { value: "response_deadline", label: "Deadline (Soonest)" },
    { value: "ai_estimated_value_high", label: "Value (Highest)" },
    { value: "likelihood_score", label: "Score (Best Match)" },
    { value: "title", label: "Title (A-Z)" },
  ];

  return (
    <>
      <PageMeta title="Opportunities | BidKing" description="Browse federal contract opportunities" />
      <PageBreadcrumb pageTitle="Opportunities" />

      <div className="space-y-6">
        {/* Search and Filters */}
        <div className="p-5 bg-white rounded-lg shadow-sm dark:bg-gray-800">
          <form onSubmit={handleSearch} className="space-y-4">
            {/* Main Search Row */}
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
              <div className="flex-1">
                <Label>Search Opportunities</Label>
                <Input
                  type="text"
                  placeholder="Search by keyword, title, solicitation number..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                />
              </div>
              {/* Quick filters and search buttons */}
              <div className="flex gap-2 lg:self-end flex-wrap">
                <button
                  type="button"
                  onClick={handleLowCompetitionToggle}
                  className={`px-4 py-2.5 text-sm rounded-lg flex items-center gap-2 transition-colors ${
                    lowCompetitionMode
                      ? "bg-green-600 text-white hover:bg-green-700"
                      : "border border-green-600 text-green-600 hover:bg-green-50 dark:border-green-500 dark:text-green-500 dark:hover:bg-green-900/20"
                  }`}
                  title="Filter to underserved NAICS codes with lower competition"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                  Low Competition
                </button>
                <Button type="submit" size="sm">
                  Search
                </Button>
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="px-4 py-2.5 text-sm border rounded-lg hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700 flex items-center gap-2"
                >
                  <svg className={`w-4 h-4 transition-transform ${showAdvanced ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                  Filters
                  {activeFilterCount > 0 && (
                    <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 rounded-full dark:bg-blue-900 dark:text-blue-200">
                      {activeFilterCount}
                    </span>
                  )}
                </button>
                {activeFilterCount > 0 && (
                  <Button type="button" size="sm" variant="outline" onClick={handleClearAll}>
                    Clear All
                  </Button>
                )}
                <Button type="button" size="sm" variant="outline" onClick={handleExportCSV}>
                  <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Export CSV
                </Button>
                {/* Saved Searches - only for authenticated users */}
                {isAuthenticated && (
                  <>
                    {/* Load Search Dropdown */}
                    <div className="relative" ref={savedSearchesDropdownRef}>
                      <button
                        type="button"
                        onClick={() => setShowSavedSearchesDropdown(!showSavedSearchesDropdown)}
                        className="px-4 py-2.5 text-sm border rounded-lg hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700 flex items-center gap-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
                        </svg>
                        Load Search
                        {savedSearches.length > 0 && (
                          <span className="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-800 rounded dark:bg-blue-900 dark:text-blue-200">
                            {savedSearches.length}
                          </span>
                        )}
                      </button>
                      {showSavedSearchesDropdown && (
                        <div className="absolute right-0 z-50 mt-2 w-72 bg-white border rounded-lg shadow-lg dark:bg-gray-800 dark:border-gray-700">
                          <div className="p-2">
                            {savedSearches.length === 0 ? (
                              <p className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                                No saved searches yet
                              </p>
                            ) : (
                              <div className="max-h-64 overflow-y-auto">
                                {savedSearches.map((search) => (
                                  <div
                                    key={search.id}
                                    onClick={() => applySavedSearch(search)}
                                    className="flex items-center justify-between px-3 py-2 text-sm rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700"
                                  >
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2">
                                        <span className="font-medium truncate">{search.name}</span>
                                        {search.is_default && (
                                          <span className="px-1.5 py-0.5 text-xs bg-green-100 text-green-800 rounded dark:bg-green-900/30 dark:text-green-400">
                                            Default
                                          </span>
                                        )}
                                      </div>
                                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                                        Used {search.use_count} times
                                      </p>
                                    </div>
                                    <button
                                      onClick={(e) => handleDeleteSavedSearch(search.id, e)}
                                      className="p-1 text-gray-400 hover:text-red-500"
                                      title="Delete"
                                    >
                                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                      </svg>
                                    </button>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                    {/* Save Search Button */}
                    <button
                      type="button"
                      onClick={() => setShowSaveModal(true)}
                      className="px-4 py-2.5 text-sm border border-blue-500 text-blue-600 rounded-lg hover:bg-blue-50 dark:border-blue-400 dark:text-blue-400 dark:hover:bg-blue-900/20 flex items-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                      </svg>
                      Save Search
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Advanced Filters */}
            {showAdvanced && (
              <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                  {/* NAICS Code */}
                  <div>
                    <Label>NAICS Code</Label>
                    {filterStats?.top_naics && filterStats.top_naics.length > 0 ? (
                      <SearchableSelect
                        options={filterStats.top_naics.map((n) => ({
                          value: n.code,
                          label: `${n.code} (${n.count})`,
                        }))}
                        placeholder="All NAICS Codes"
                        value={naicsFilter}
                        onChange={setNaicsFilter}
                      />
                    ) : (
                      <Input
                        type="text"
                        placeholder="e.g., 541511"
                        value={naicsFilter}
                        onChange={(e) => setNaicsFilter(e.target.value)}
                      />
                    )}
                  </div>

                  {/* Agency */}
                  <div>
                    <Label>Agency</Label>
                    {filterStats?.top_agencies && filterStats.top_agencies.length > 0 ? (
                      <SearchableSelect
                        options={filterStats.top_agencies.map((a) => ({
                          value: a.name,
                          label: `${a.name.length > 40 ? a.name.substring(0, 40) + "..." : a.name} (${a.count})`,
                        }))}
                        placeholder="All Agencies"
                        value={agencyFilter}
                        onChange={setAgencyFilter}
                      />
                    ) : (
                      <Input
                        type="text"
                        placeholder="Agency name..."
                        value={agencyFilter}
                        onChange={(e) => setAgencyFilter(e.target.value)}
                      />
                    )}
                  </div>

                  {/* Set-Aside Type */}
                  <div>
                    <Label>Set-Aside Type</Label>
                    <SearchableSelect
                      options={setAsideTypes.map((sa) => ({
                        value: sa.value,
                        label: sa.label,
                      }))}
                      placeholder="All Set-Asides"
                      value={setAsideFilter}
                      onChange={setSetAsideFilter}
                    />
                  </div>

                  {/* State */}
                  <div>
                    <Label>State</Label>
                    <SearchableSelect
                      options={usStates.map((state) => ({
                        value: state,
                        label: state,
                      }))}
                      placeholder="All States"
                      value={stateFilter}
                      onChange={setStateFilter}
                    />
                  </div>
                </div>

                {/* AI Estimated Value Filters */}
                <div className="grid grid-cols-1 gap-4 mt-4 md:grid-cols-5">
                  <div>
                    <Label>Notice Type</Label>
                    <SearchableSelect
                      options={noticeTypes.map((nt) => ({
                        value: nt.value,
                        label: nt.label,
                      }))}
                      placeholder="All Notice Types"
                      value={noticeTypeFilter}
                      onChange={setNoticeTypeFilter}
                    />
                  </div>
                  <div>
                    <Label>Min Estimated Value ($)</Label>
                    <Input
                      type="number"
                      placeholder="e.g., 50000"
                      value={minValue}
                      onChange={(e) => setMinValue(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label>Max Estimated Value ($)</Label>
                    <Input
                      type="number"
                      placeholder="e.g., 500000"
                      value={maxValue}
                      onChange={(e) => setMaxValue(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label>Has Value Estimate</Label>
                    <select
                      value={hasValueEstimate}
                      onChange={(e) => setHasValueEstimate(e.target.value as "all" | "yes" | "no")}
                      className="w-full h-11 px-4 py-2.5 text-sm bg-transparent border border-gray-300 rounded-lg appearance-none dark:border-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:text-white"
                    >
                      <option value="all">All Opportunities</option>
                      <option value="yes">With AI Estimate Only</option>
                      <option value="no">Without AI Estimate</option>
                    </select>
                  </div>
                  <div>
                    <Label>Has AI Analysis</Label>
                    <select
                      value={hasAiAnalysis}
                      onChange={(e) => setHasAiAnalysis(e.target.value as "all" | "yes" | "no")}
                      className="w-full h-11 px-4 py-2.5 text-sm bg-transparent border border-gray-300 rounded-lg appearance-none dark:border-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:text-white"
                    >
                      <option value="all">All Opportunities</option>
                      <option value="yes">With AI Analysis Only</option>
                      <option value="no">Without AI Analysis</option>
                    </select>
                  </div>
                </div>

                {/* Stats Summary */}
                {filterStats && (
                  <div className="flex flex-wrap items-center gap-4 pt-4 mt-4 border-t border-gray-100 dark:border-gray-700">
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      <span className="font-medium text-gray-900 dark:text-white">{filterStats.total_active}</span> active opportunities
                    </span>
                    {filterStats.new_today > 0 && (
                      <span className="px-2 py-1 text-xs font-medium text-green-800 bg-green-100 rounded dark:bg-green-900/30 dark:text-green-400">
                        {filterStats.new_today} new today
                      </span>
                    )}
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      Score: <span className="text-green-600">{filterStats.score_distribution.high} high</span> /
                      <span className="text-yellow-600"> {filterStats.score_distribution.medium} med</span> /
                      <span className="text-red-600"> {filterStats.score_distribution.low} low</span>
                    </span>
                  </div>
                )}
              </div>
            )}
          </form>
        </div>

        {/* Results summary and Sort Dropdown */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Showing {opportunities.length} of {total} opportunities
          </p>
          <div className="flex items-center gap-4">
            {/* Early Stage Toggle */}
            <button
              type="button"
              onClick={() => { setEarlyStageOnly(!earlyStageOnly); setPage(1); }}
              className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1.5 transition-colors ${
                earlyStageOnly
                  ? "bg-purple-600 text-white hover:bg-purple-700"
                  : "border border-purple-500 text-purple-600 hover:bg-purple-50 dark:border-purple-400 dark:text-purple-400 dark:hover:bg-purple-900/20"
              }`}
              title="Show only Sources Sought & Presolicitation opportunities"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Early Stage
            </button>
            {/* Include Expired Toggle */}
            <button
              type="button"
              onClick={() => { setIncludeExpired(!includeExpired); setPage(1); }}
              className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1.5 transition-colors ${
                includeExpired
                  ? "bg-orange-600 text-white hover:bg-orange-700"
                  : "border border-orange-500 text-orange-600 hover:bg-orange-50 dark:border-orange-400 dark:text-orange-400 dark:hover:bg-orange-900/20"
              }`}
              title="Include opportunities past their deadline"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Include Expired
            </button>
            {/* Sort Dropdown */}
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">Sort by:</label>
              <select
                value={currentSort}
                onChange={(e) => { setCurrentSort(e.target.value); setCurrentOrder(e.target.value === "title" ? "asc" : "desc"); }}
                className="h-9 px-3 py-1.5 text-sm bg-transparent border border-gray-300 rounded-lg appearance-none dark:border-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:text-white"
              >
                {sortOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div className="p-4 text-red-600 bg-red-50 rounded-lg dark:bg-red-900/20 dark:text-red-400">
            {error}
          </div>
        )}

        {/* Loading state */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-4 border-blue-500 rounded-full animate-spin border-t-transparent"></div>
          </div>
        ) : (
          /* Opportunities table */
          <div className="overflow-hidden bg-white rounded-lg shadow dark:bg-gray-800">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-900">
                  <tr>
                    <SortableHeader
                      column="title"
                      label="Opportunity"
                      currentSort={currentSort}
                      currentOrder={currentOrder}
                      onSort={handleColumnSort}
                    />
                    <SortableHeader
                      column="agency_name"
                      label="Agency"
                      currentSort={currentSort}
                      currentOrder={currentOrder}
                      onSort={handleColumnSort}
                    />
                    <SortableHeader
                      column="naics_code"
                      label="NAICS"
                      currentSort={currentSort}
                      currentOrder={currentOrder}
                      onSort={handleColumnSort}
                    />
                    <SortableHeader
                      column="likelihood_score"
                      label={isAuthenticated ? "Your Fit" : "Score"}
                      currentSort={currentSort}
                      currentOrder={currentOrder}
                      onSort={handleColumnSort}
                    />
                    <SortableHeader
                      column="posted_date"
                      label="Posted"
                      currentSort={currentSort}
                      currentOrder={currentOrder}
                      onSort={handleColumnSort}
                    />
                    <SortableHeader
                      column="response_deadline"
                      label="Deadline"
                      currentSort={currentSort}
                      currentOrder={currentOrder}
                      onSort={handleColumnSort}
                    />
                    <th className="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {sortedOpportunities.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                        No opportunities found. Try adjusting your search filters.
                      </td>
                    </tr>
                  ) : (
                    sortedOpportunities.map((opp) => (
                      <tr key={opp.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                        <td className="px-6 py-4">
                          <div className="max-w-md">
                            <Link
                              to={`/opportunities/${opp.id}`}
                              className="font-medium text-gray-900 dark:text-white hover:text-brand-500"
                            >
                              {opp.title}
                            </Link>
                            <p className="mt-1 text-xs text-gray-500 truncate dark:text-gray-400">
                              {opp.solicitation_number || opp.notice_id}
                            </p>
                            {opp.set_aside_type && (
                              <span className="inline-block px-2 py-0.5 mt-1 text-xs bg-blue-100 text-blue-800 rounded dark:bg-blue-900/30 dark:text-blue-400">
                                {opp.set_aside_description || opp.set_aside_type}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm text-gray-900 dark:text-white">
                            {opp.agency_name || "N/A"}
                          </div>
                          {opp.office_name && (
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              {opp.office_name}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm font-mono text-gray-900 dark:text-white">
                            {opp.naics_code || "N/A"}
                          </div>
                          {opp.naics_description && (
                            <div className="text-xs text-gray-500 dark:text-gray-400 max-w-[150px] truncate">
                              {opp.naics_description}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          {/* Show personalized score if available, otherwise use likelihood_score - unified format */}
                          {isAuthenticated && personalizedScores[opp.id] ? (
                            <PersonalizedScoreBadge score={personalizedScores[opp.id]} />
                          ) : (
                            <ScoreBadge score={opp.likelihood_score || 50} />
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm text-gray-900 dark:text-white">
                            {formatDate(opp.posted_date)}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm text-gray-900 dark:text-white">
                            {formatDate(opp.response_deadline)}
                          </div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            {getDaysUntil(opp.response_deadline)}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex gap-2">
                            <Link
                              to={`/opportunities/${opp.id}`}
                              className="text-sm text-brand-500 hover:text-brand-600"
                            >
                              View
                            </Link>
                            {opp.ui_link && (
                              <a
                                href={opp.ui_link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm text-gray-500 hover:text-gray-700"
                              >
                                SAM.gov
                              </a>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-6 py-3 border-t border-gray-200 dark:border-gray-700">
                <div className="text-sm text-gray-500">
                  Page {page} of {totalPages}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(page - 1)}
                    disabled={page === 1}
                    className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed dark:border-gray-600 dark:hover:bg-gray-700"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(page + 1)}
                    disabled={page === totalPages}
                    className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed dark:border-gray-600 dark:hover:bg-gray-700"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Save Search Modal */}
      {showSaveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="w-full max-w-md p-6 bg-white rounded-lg shadow-xl dark:bg-gray-800">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                Save Current Search
              </h3>
              <button
                onClick={() => setShowSaveModal(false)}
                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <Label>Search Name</Label>
                <Input
                  type="text"
                  value={saveSearchName}
                  onChange={(e) => setSaveSearchName(e.target.value)}
                  placeholder="e.g., My IT Contracts Filter"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="saveAsDefault"
                  checked={saveAsDefault}
                  onChange={(e) => setSaveAsDefault(e.target.checked)}
                  className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                />
                <label htmlFor="saveAsDefault" className="text-sm text-gray-700 dark:text-gray-300">
                  Set as default search
                </label>
              </div>
              {/* Show current filters summary */}
              <div className="p-3 text-sm bg-gray-50 rounded dark:bg-gray-700/50">
                <p className="font-medium text-gray-700 dark:text-gray-300 mb-2">Current Filters:</p>
                <div className="flex flex-wrap gap-1">
                  {searchInput && <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs dark:bg-blue-900/30 dark:text-blue-400">Query: "{searchInput}"</span>}
                  {naicsFilter && <span className="px-2 py-0.5 bg-green-100 text-green-800 rounded text-xs dark:bg-green-900/30 dark:text-green-400">NAICS: {naicsFilter}</span>}
                  {agencyFilter && <span className="px-2 py-0.5 bg-purple-100 text-purple-800 rounded text-xs dark:bg-purple-900/30 dark:text-purple-400">Agency: {agencyFilter.substring(0, 20)}...</span>}
                  {setAsideFilter && <span className="px-2 py-0.5 bg-orange-100 text-orange-800 rounded text-xs dark:bg-orange-900/30 dark:text-orange-400">Set-Aside: {setAsideFilter}</span>}
                  {stateFilter && <span className="px-2 py-0.5 bg-cyan-100 text-cyan-800 rounded text-xs dark:bg-cyan-900/30 dark:text-cyan-400">State: {stateFilter}</span>}
                  {noticeTypeFilter && <span className="px-2 py-0.5 bg-yellow-100 text-yellow-800 rounded text-xs dark:bg-yellow-900/30 dark:text-yellow-400">Type: {noticeTypeFilter}</span>}
                  {minValue && <span className="px-2 py-0.5 bg-gray-200 text-gray-800 rounded text-xs dark:bg-gray-600 dark:text-gray-300">Min: ${minValue}</span>}
                  {maxValue && <span className="px-2 py-0.5 bg-gray-200 text-gray-800 rounded text-xs dark:bg-gray-600 dark:text-gray-300">Max: ${maxValue}</span>}
                  {earlyStageOnly && <span className="px-2 py-0.5 bg-purple-100 text-purple-800 rounded text-xs dark:bg-purple-900/30 dark:text-purple-400">Early Stage</span>}
                  {!searchInput && !naicsFilter && !agencyFilter && !setAsideFilter && !stateFilter && !noticeTypeFilter && !minValue && !maxValue && !earlyStageOnly && (
                    <span className="text-gray-500 dark:text-gray-400">No filters applied</span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <Button
                type="button"
                variant="outline"
                onClick={() => { setShowSaveModal(false); setSaveSearchName(""); setSaveAsDefault(false); }}
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleSaveSearch}
                disabled={!saveSearchName.trim()}
              >
                Save Search
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
