import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useOpportunitiesStore } from "../../stores/opportunitiesStore";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";
import Input from "../../components/form/input/InputField";
import Label from "../../components/form/Label";
import Button from "../../components/ui/button/Button";
import SearchableSelect from "../../components/form/SearchableSelect";

interface FilterStats {
  total_active: number;
  new_today: number;
  score_distribution: { high: number; medium: number; low: number };
  top_agencies: { name: string; count: number }[];
  top_naics: { code: string; count: number }[];
}

// Score badge component
function ScoreBadge({ score }: { score: number }) {
  const getScoreColor = () => {
    if (score >= 70) return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
    if (score >= 40) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
    return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
  };

  const getScoreLabel = () => {
    if (score >= 70) return "High";
    if (score >= 40) return "Medium";
    return "Low";
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded ${getScoreColor()}`}>
      <span className="font-bold">{score}</span>
      <span className="text-xs opacity-75">{getScoreLabel()}</span>
    </span>
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
  const {
    opportunities,
    isLoading,
    error,
    total,
    page,
    pageSize,
    filters,
    fetchOpportunities,
    setFilters,
    setPage,
    clearFilters,
  } = useOpportunitiesStore();

  const [searchInput, setSearchInput] = useState(filters.keywords || "");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [filterStats, setFilterStats] = useState<FilterStats | null>(null);
  const [naicsFilter, setNaicsFilter] = useState("");
  const [agencyFilter, setAgencyFilter] = useState("");
  const [setAsideFilter, setSetAsideFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");

  // Get current sort from filters
  const currentSort = filters.sort_by || "response_deadline";
  const currentOrder = filters.sort_order || "asc";

  useEffect(() => {
    fetchOpportunities();
    fetchFilterStats();
  }, [page, filters]);

  // Handle column sort
  const handleColumnSort = (column: string) => {
    const newOrder = currentSort === column && currentOrder === "asc" ? "desc" : "asc";
    setFilters({ sort_by: column, sort_order: newOrder });
  };

  const fetchFilterStats = async () => {
    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "https://bidking-api.fly.dev/api/v1"}/opportunities/stats`
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
    const newFilters: Record<string, unknown> = { keywords: searchInput };
    if (naicsFilter) newFilters.naics_codes = [naicsFilter];
    if (agencyFilter) newFilters.agencies = [agencyFilter];
    if (setAsideFilter) newFilters.set_aside = setAsideFilter;
    if (stateFilter) newFilters.state = stateFilter;
    setFilters(newFilters);
  };

  const handleClearAll = () => {
    setSearchInput("");
    setNaicsFilter("");
    setAgencyFilter("");
    setSetAsideFilter("");
    setStateFilter("");
    clearFilters();
  };

  const activeFilterCount = [
    searchInput,
    naicsFilter,
    agencyFilter,
    setAsideFilter,
    stateFilter,
    filters.min_score && filters.min_score > 0 ? "score" : "",
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
              <div className="w-full lg:w-40">
                <Label>Min Score</Label>
                <select
                  className="w-full px-4 py-2.5 text-sm border rounded-lg dark:bg-gray-900 dark:border-gray-700"
                  value={filters.min_score || ""}
                  onChange={(e) => setFilters({ min_score: e.target.value ? Number(e.target.value) : undefined })}
                >
                  <option value="">Any Score</option>
                  <option value="70">High (70+)</option>
                  <option value="40">Medium (40+)</option>
                </select>
              </div>
              <div className="flex gap-2 lg:self-end">
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

        {/* Results summary */}
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Showing {opportunities.length} of {total} opportunities
          </p>
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
                      label="Score"
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
                  {opportunities.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                        No opportunities found. Try adjusting your search filters.
                      </td>
                    </tr>
                  ) : (
                    opportunities.map((opp) => (
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
                          <ScoreBadge score={opp.likelihood_score} />
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
    </>
  );
}
