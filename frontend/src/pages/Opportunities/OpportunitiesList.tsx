import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useOpportunitiesStore } from "../../stores/opportunitiesStore";
import PageBreadcrumb from "../../components/common/PageBreadcrumb";
import PageMeta from "../../components/common/PageMeta";
import Input from "../../components/form/input/InputField";
import Label from "../../components/form/Label";
import Button from "../../components/ui/button/Button";

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

  useEffect(() => {
    fetchOpportunities();
  }, [page, filters]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setFilters({ keywords: searchInput });
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <>
      <PageMeta title="Opportunities | BidKing" description="Browse federal contract opportunities" />
      <PageBreadcrumb pageTitle="Opportunities" />

      <div className="space-y-6">
        {/* Search and Filters */}
        <div className="p-5 bg-white rounded-lg shadow-sm dark:bg-gray-800">
          <form onSubmit={handleSearch} className="flex flex-col gap-4 lg:flex-row lg:items-end">
            <div className="flex-1">
              <Label>Search Opportunities</Label>
              <Input
                type="text"
                placeholder="Search by keyword, NAICS code, agency..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>
            <div className="w-full lg:w-48">
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
            <div className="flex gap-2">
              <Button type="submit" size="sm">
                Search
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setSearchInput("");
                  clearFilters();
                }}
              >
                Clear
              </Button>
            </div>
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
                    <th className="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase">
                      Opportunity
                    </th>
                    <th className="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase">
                      Agency
                    </th>
                    <th className="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase">
                      NAICS
                    </th>
                    <th className="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase">
                      Score
                    </th>
                    <th className="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase">
                      Deadline
                    </th>
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
                            {opp.sam_gov_link && (
                              <a
                                href={opp.sam_gov_link}
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
