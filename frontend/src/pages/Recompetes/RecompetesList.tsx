import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";
import Input from "../../components/form/input/InputField";
import Label from "../../components/form/Label";
import Button from "../../components/ui/button/Button";

interface FilterOptions {
  agencies: { name: string; count: number }[];
  naics_codes: { code: string; count: number }[];
  value_range: { min: number; max: number; avg: number };
}

interface Recompete {
  id: string;
  award_id: string;
  piid: string;
  period_of_performance_end: string;
  days_until_expiration: number;
  naics_code: string;
  total_value: number | null;
  awarding_agency_name: string;
  incumbent_name: string;
  status: string;
}

interface RecompetesResponse {
  items: Recompete[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  days_ahead: number;
}

// Format currency
function formatCurrency(value: number | null): string {
  if (!value) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
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

// Days badge
function DaysBadge({ days }: { days: number }) {
  const getColor = () => {
    if (days <= 30) return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
    if (days <= 90) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
    return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
  };

  return (
    <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded ${getColor()}`}>
      {days} days
    </span>
  );
}

// Sort icon component
function SortIcon({ column, currentSort, currentOrder }: { column: string; currentSort: string; currentOrder: string }) {
  const isActive = currentSort === column;

  return (
    <span className="inline-flex flex-col ml-1">
      <svg
        className={`w-3 h-3 -mb-1 ${isActive && currentOrder === "asc" ? "text-blue-600 dark:text-blue-400" : "text-gray-400"}`}
        fill="currentColor"
        viewBox="0 0 20 20"
      >
        <path d="M5 12l5-5 5 5H5z" />
      </svg>
      <svg
        className={`w-3 h-3 ${isActive && currentOrder === "desc" ? "text-blue-600 dark:text-blue-400" : "text-gray-400"}`}
        fill="currentColor"
        viewBox="0 0 20 20"
      >
        <path d="M5 8l5 5 5-5H5z" />
      </svg>
    </span>
  );
}

// Sortable column header component
function SortableHeader({
  label,
  column,
  currentSort,
  currentOrder,
  onSort
}: {
  label: string;
  column: string;
  currentSort: string;
  currentOrder: string;
  onSort: (column: string) => void;
}) {
  const isActive = currentSort === column;

  return (
    <th
      className={`px-6 py-3 text-xs font-medium tracking-wider text-left uppercase cursor-pointer select-none hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors ${
        isActive ? "text-blue-600 dark:text-blue-400" : "text-gray-500"
      }`}
      onClick={() => onSort(column)}
    >
      <div className="flex items-center">
        {label}
        <SortIcon column={column} currentSort={currentSort} currentOrder={currentOrder} />
      </div>
    </th>
  );
}

export default function RecompetesList() {
  const navigate = useNavigate();
  const [recompetes, setRecompetes] = useState<Recompete[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const PAGE_SIZE = 25;

  // Filter states
  const [searchQuery, setSearchQuery] = useState("");
  const [naicsFilter, setNaicsFilter] = useState("");
  const [agencyFilter, setAgencyFilter] = useState("");
  const [daysAhead, setDaysAhead] = useState(365);
  const [minValue, setMinValue] = useState("");
  const [maxValue, setMaxValue] = useState("");
  const [sortBy, setSortBy] = useState("expiration");
  const [sortOrder, setSortOrder] = useState("asc");
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Filter options from API
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);

  const fetchRecompetes = async (pageNum: number = page) => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        days_ahead: daysAhead.toString(),
        page: pageNum.toString(),
        page_size: PAGE_SIZE.toString(),
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      if (searchQuery) params.append("search", searchQuery);
      if (naicsFilter) params.append("naics_code", naicsFilter);
      if (agencyFilter) params.append("agency", agencyFilter);
      if (minValue) params.append("min_value", minValue);
      if (maxValue) params.append("max_value", maxValue);

      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1"}/public/recompetes?${params}`
      );

      if (!response.ok) {
        throw new Error("Failed to fetch recompetes");
      }

      const data: RecompetesResponse = await response.json();
      setRecompetes(data.items);
      setTotal(data.total);
      setPage(data.page);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load recompetes");
    } finally {
      setIsLoading(false);
    }
  };

  const fetchFilterOptions = async () => {
    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1"}/public/recompetes/filters`
      );
      if (response.ok) {
        const data = await response.json();
        setFilterOptions(data);
      }
    } catch {
      // Silently fail - filter options are optional
    }
  };

  useEffect(() => {
    fetchRecompetes();
    fetchFilterOptions();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchRecompetes(1);
  };

  const goToPage = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setPage(newPage);
      fetchRecompetes(newPage);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const clearAllFilters = () => {
    setSearchQuery("");
    setNaicsFilter("");
    setAgencyFilter("");
    setDaysAhead(365);
    setMinValue("");
    setMaxValue("");
    setSortBy("expiration");
    setSortOrder("asc");
    setPage(1);
    // Fetch with cleared filters
    setTimeout(() => fetchRecompetes(1), 0);
  };

  const handleExportCSV = async () => {
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append("search", searchQuery);
      if (naicsFilter) params.append("naics_code", naicsFilter);
      if (agencyFilter) params.append("agency", agencyFilter);
      if (minValue) params.append("min_value", minValue);
      if (maxValue) params.append("max_value", maxValue);
      params.append("days_ahead", daysAhead.toString());

      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "https://api.bidking.ai"}/api/v1/public/recompetes/export/csv?${params}`
      );

      if (!response.ok) throw new Error("Export failed");

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `bidking_recompetes_${new Date().toISOString().split("T")[0]}.csv`;
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
    searchQuery,
    naicsFilter,
    agencyFilter,
    minValue,
    maxValue,
    daysAhead !== 365 ? "days" : "",
  ].filter(Boolean).length;

  // Handle column header click for sorting
  const handleColumnSort = (column: string) => {
    const newSortOrder = sortBy === column && sortOrder === "asc" ? "desc" : "asc";
    setSortBy(column);
    setSortOrder(newSortOrder);
    setPage(1);
    // Fetch with new sort params immediately
    fetchRecompetesWithSort(column, newSortOrder);
  };

  // Fetch with specific sort parameters (used by column header clicks)
  const fetchRecompetesWithSort = async (newSortBy: string, newSortOrder: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        days_ahead: daysAhead.toString(),
        page: "1",
        page_size: PAGE_SIZE.toString(),
        sort_by: newSortBy,
        sort_order: newSortOrder,
      });
      if (searchQuery) params.append("search", searchQuery);
      if (naicsFilter) params.append("naics_code", naicsFilter);
      if (agencyFilter) params.append("agency", agencyFilter);
      if (minValue) params.append("min_value", minValue);
      if (maxValue) params.append("max_value", maxValue);

      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1"}/public/recompetes?${params}`
      );

      if (!response.ok) {
        throw new Error("Failed to fetch recompetes");
      }

      const data: RecompetesResponse = await response.json();
      setRecompetes(data.items);
      setTotal(data.total);
      setPage(data.page);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load recompetes");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <PageMeta title="Recompetes | BidKing" description="Expiring contracts that will be re-bid" />
      <PageBreadcrumb pageTitle="Recompetes" />

      <div className="space-y-6">
        {/* Info banner */}
        <div className="p-4 bg-blue-50 rounded-lg dark:bg-blue-900/20">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-medium text-blue-800 dark:text-blue-300">
                Recompete Opportunities
              </h3>
              <p className="mt-1 text-sm text-blue-700 dark:text-blue-400">
                These are existing federal contracts that are expiring soon. When a contract expires,
                the government typically issues a new solicitation (recompete). Track these to get early
                notice of upcoming opportunities before they're posted on SAM.gov.
              </p>
            </div>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="p-5 bg-white rounded-lg shadow-sm dark:bg-gray-800">
          <form onSubmit={handleSearch} className="space-y-4">
            {/* Main Search Row */}
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
              <div className="flex-1">
                <Label>Search</Label>
                <Input
                  type="text"
                  placeholder="Search by contract ID, agency, incumbent..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <div className="w-full lg:w-40">
                <Label>Expires Within</Label>
                <select
                  className="w-full px-4 py-2.5 text-sm border rounded-lg dark:bg-gray-900 dark:border-gray-700"
                  value={daysAhead}
                  onChange={(e) => setDaysAhead(Number(e.target.value))}
                >
                  <option value="30">30 days</option>
                  <option value="90">90 days</option>
                  <option value="180">180 days</option>
                  <option value="365">1 year</option>
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
                  <Button type="button" size="sm" variant="outline" onClick={clearAllFilters}>
                    Clear All
                  </Button>
                )}
                <Button type="button" size="sm" variant="outline" onClick={handleExportCSV}>
                  <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Export CSV
                </Button>
              </div>
            </div>

            {/* Advanced Filters */}
            {showAdvanced && (
              <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                  {/* NAICS Code */}
                  <div>
                    <Label>NAICS Code</Label>
                    {filterOptions?.naics_codes && filterOptions.naics_codes.length > 0 ? (
                      <select
                        className="w-full px-4 py-2.5 text-sm border rounded-lg dark:bg-gray-900 dark:border-gray-700"
                        value={naicsFilter}
                        onChange={(e) => setNaicsFilter(e.target.value)}
                      >
                        <option value="">All NAICS Codes</option>
                        {filterOptions.naics_codes.map((n) => (
                          <option key={n.code} value={n.code}>
                            {n.code} ({n.count})
                          </option>
                        ))}
                      </select>
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
                    {filterOptions?.agencies && filterOptions.agencies.length > 0 ? (
                      <select
                        className="w-full px-4 py-2.5 text-sm border rounded-lg dark:bg-gray-900 dark:border-gray-700"
                        value={agencyFilter}
                        onChange={(e) => setAgencyFilter(e.target.value)}
                      >
                        <option value="">All Agencies</option>
                        {filterOptions.agencies.map((a) => (
                          <option key={a.name} value={a.name}>
                            {a.name.length > 40 ? a.name.substring(0, 40) + "..." : a.name} ({a.count})
                          </option>
                        ))}
                      </select>
                    ) : (
                      <Input
                        type="text"
                        placeholder="Agency name..."
                        value={agencyFilter}
                        onChange={(e) => setAgencyFilter(e.target.value)}
                      />
                    )}
                  </div>

                  {/* Min Value */}
                  <div>
                    <Label>Min Value ($)</Label>
                    <Input
                      type="number"
                      placeholder="e.g., 100000"
                      value={minValue}
                      onChange={(e) => setMinValue(e.target.value)}
                    />
                  </div>

                  {/* Max Value */}
                  <div>
                    <Label>Max Value ($)</Label>
                    <Input
                      type="number"
                      placeholder="e.g., 10000000"
                      value={maxValue}
                      onChange={(e) => setMaxValue(e.target.value)}
                    />
                  </div>

                  {/* Sort By */}
                  <div>
                    <Label>Sort By</Label>
                    <select
                      className="w-full px-4 py-2.5 text-sm border rounded-lg dark:bg-gray-900 dark:border-gray-700"
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value)}
                    >
                      <option value="expiration">Expiration Date</option>
                      <option value="value">Contract Value</option>
                      <option value="agency">Agency Name</option>
                      <option value="contract">Contract ID</option>
                      <option value="incumbent">Incumbent Name</option>
                      <option value="naics">NAICS Code</option>
                    </select>
                  </div>

                  {/* Sort Order */}
                  <div>
                    <Label>Order</Label>
                    <select
                      className="w-full px-4 py-2.5 text-sm border rounded-lg dark:bg-gray-900 dark:border-gray-700"
                      value={sortOrder}
                      onChange={(e) => setSortOrder(e.target.value)}
                    >
                      <option value="asc">Ascending</option>
                      <option value="desc">Descending</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </form>
        </div>

        {/* Results summary */}
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Showing {((page - 1) * PAGE_SIZE) + 1}-{Math.min(page * PAGE_SIZE, total)} of {total} expiring contracts
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Page {page} of {totalPages}
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
          <>
            {/* Recompetes table */}
            <div className="overflow-hidden bg-white rounded-lg shadow dark:bg-gray-800">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-gray-900">
                    <tr>
                      <SortableHeader
                        label="Contract"
                        column="contract"
                        currentSort={sortBy}
                        currentOrder={sortOrder}
                        onSort={handleColumnSort}
                      />
                      <SortableHeader
                        label="Agency"
                        column="agency"
                        currentSort={sortBy}
                        currentOrder={sortOrder}
                        onSort={handleColumnSort}
                      />
                      <SortableHeader
                        label="Incumbent"
                        column="incumbent"
                        currentSort={sortBy}
                        currentOrder={sortOrder}
                        onSort={handleColumnSort}
                      />
                      <SortableHeader
                        label="NAICS"
                        column="naics"
                        currentSort={sortBy}
                        currentOrder={sortOrder}
                        onSort={handleColumnSort}
                      />
                      <SortableHeader
                        label="Value"
                        column="value"
                        currentSort={sortBy}
                        currentOrder={sortOrder}
                        onSort={handleColumnSort}
                      />
                      <SortableHeader
                        label="Expires"
                        column="expiration"
                        currentSort={sortBy}
                        currentOrder={sortOrder}
                        onSort={handleColumnSort}
                      />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {recompetes.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                          No recompetes found. Try adjusting your filters.
                        </td>
                      </tr>
                    ) : (
                      recompetes.map((recompete) => (
                        <tr
                          key={recompete.id}
                          className="hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
                          onClick={() => navigate(`/recompetes/${recompete.id}`)}
                        >
                          <td className="px-6 py-4">
                            <div>
                              <p className="font-medium text-blue-600 dark:text-blue-400 hover:underline">
                                {recompete.piid}
                              </p>
                              <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                                {recompete.award_id}
                              </p>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="text-sm text-gray-900 dark:text-white max-w-[200px]">
                              {recompete.awarding_agency_name || "N/A"}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="text-sm text-gray-900 dark:text-white max-w-[200px]">
                              {recompete.incumbent_name || "N/A"}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="text-sm font-mono text-gray-900 dark:text-white">
                              {recompete.naics_code || "N/A"}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="text-sm text-gray-900 dark:text-white">
                              {formatCurrency(recompete.total_value)}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex flex-col gap-1">
                              <DaysBadge days={recompete.days_until_expiration} />
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                {formatDate(recompete.period_of_performance_end)}
                              </span>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 bg-white rounded-lg shadow dark:bg-gray-800 sm:px-6">
                <div className="flex justify-between flex-1 sm:hidden">
                  <button
                    onClick={() => goToPage(page - 1)}
                    disabled={page === 1}
                    className="relative inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => goToPage(page + 1)}
                    disabled={page === totalPages}
                    className="relative inline-flex items-center px-4 py-2 ml-3 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
                  >
                    Next
                  </button>
                </div>
                <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      Showing <span className="font-medium">{((page - 1) * PAGE_SIZE) + 1}</span> to{" "}
                      <span className="font-medium">{Math.min(page * PAGE_SIZE, total)}</span> of{" "}
                      <span className="font-medium">{total}</span> results
                    </p>
                  </div>
                  <div>
                    <nav className="inline-flex -space-x-px rounded-md shadow-sm" aria-label="Pagination">
                      <button
                        onClick={() => goToPage(1)}
                        disabled={page === 1}
                        className="relative inline-flex items-center px-2 py-2 text-gray-400 bg-white border border-gray-300 rounded-l-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-gray-700 dark:border-gray-600"
                      >
                        <span className="sr-only">First</span>
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M15.707 15.707a1 1 0 01-1.414 0l-5-5a1 1 0 010-1.414l5-5a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 010 1.414zm-6 0a1 1 0 01-1.414 0l-5-5a1 1 0 010-1.414l5-5a1 1 0 011.414 1.414L5.414 10l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
                        </svg>
                      </button>
                      <button
                        onClick={() => goToPage(page - 1)}
                        disabled={page === 1}
                        className="relative inline-flex items-center px-2 py-2 text-gray-400 bg-white border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-gray-700 dark:border-gray-600"
                      >
                        <span className="sr-only">Previous</span>
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      </button>

                      {/* Page numbers */}
                      {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                        let pageNum;
                        if (totalPages <= 5) {
                          pageNum = i + 1;
                        } else if (page <= 3) {
                          pageNum = i + 1;
                        } else if (page >= totalPages - 2) {
                          pageNum = totalPages - 4 + i;
                        } else {
                          pageNum = page - 2 + i;
                        }
                        return (
                          <button
                            key={pageNum}
                            onClick={() => goToPage(pageNum)}
                            className={`relative inline-flex items-center px-4 py-2 text-sm font-medium border ${
                              page === pageNum
                                ? "z-10 bg-blue-600 border-blue-600 text-white"
                                : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                            }`}
                          >
                            {pageNum}
                          </button>
                        );
                      })}

                      <button
                        onClick={() => goToPage(page + 1)}
                        disabled={page === totalPages}
                        className="relative inline-flex items-center px-2 py-2 text-gray-400 bg-white border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-gray-700 dark:border-gray-600"
                      >
                        <span className="sr-only">Next</span>
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                        </svg>
                      </button>
                      <button
                        onClick={() => goToPage(totalPages)}
                        disabled={page === totalPages}
                        className="relative inline-flex items-center px-2 py-2 text-gray-400 bg-white border border-gray-300 rounded-r-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-gray-700 dark:border-gray-600"
                      >
                        <span className="sr-only">Last</span>
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M4.293 15.707a1 1 0 010-1.414L8.586 10 4.293 6.707a1 1 0 011.414-1.414l5 5a1 1 0 010 1.414l-5 5a1 1 0 01-1.414 0zm6 0a1 1 0 010-1.414L14.586 10l-4.293-4.293a1 1 0 011.414-1.414l5 5a1 1 0 010 1.414l-5 5a1 1 0 01-1.414 0z" clipRule="evenodd" />
                        </svg>
                      </button>
                    </nav>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
