import { useEffect, useState } from "react";
import { useParams, Link } from "react-router";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";
import { getIncumbentVulnerability, IncumbentVulnerability } from "../../api/opportunities";

interface ContractDetails {
  award_type: string | null;
  award_type_description: string | null;
  total_obligation: number | null;
  base_and_all_options_value: number | null;
  award_date: string | null;
  period_of_performance_start: string | null;
  naics_description: string | null;
  psc_code: string | null;
  psc_description: string | null;
  awarding_sub_agency_name: string | null;
  awarding_office_name: string | null;
  recipient_uei: string | null;
  recipient_city: string | null;
  recipient_state: string | null;
  pop_city: string | null;
  pop_state: string | null;
  pop_zip: string | null;
  competition_type: string | null;
  number_of_offers: number | null;
  set_aside_type: string | null;
}

interface RecompeteData {
  id: string;
  award_id: string;
  piid: string;
  period_of_performance_end: string | null;
  days_until_expiration: number | null;
  naics_code: string | null;
  total_value: number | null;
  awarding_agency_name: string | null;
  incumbent_name: string | null;
  incumbent_uei: string | null;
  status: string;
  linked_opportunity_id: string | null;
  created_at: string | null;
  updated_at: string | null;
  contract_details?: ContractDetails;
  usaspending_link?: string;
}

// Enrichment Types
interface ContractHistoryItem {
  award_id: string;
  piid: string;
  parent_piid: string | null;
  award_type: string;
  award_type_description: string | null;
  award_date: string | null;
  total_obligation: number | null;
  base_and_all_options_value: number | null;
  period_of_performance_start: string | null;
  period_of_performance_end: string | null;
  recipient_name: string | null;
  awarding_agency_name: string | null;
  usaspending_link: string | null;
}

interface ContractHistoryData {
  base_piid: string;
  current_piid: string;
  total_contracts: number;
  total_obligated: number;
  contract_history: ContractHistoryItem[];
}

interface NAICSExpertise {
  code: string;
  description: string | null;
  count: number;
  total_value: number;
}

interface AgencyExpertise {
  agency: string;
  count: number;
  total_value: number;
}

interface IncumbentProfile {
  uei: string;
  name: string;
  location: {
    city: string | null;
    state: string | null;
    zip: string | null;
    country: string | null;
  } | null;
  parent_company: {
    uei: string | null;
    name: string | null;
  } | null;
  statistics: {
    total_awards: number;
    total_obligation: number;
    average_award_value: number;
    first_award_date: string | null;
    last_award_date: string | null;
  };
  primary_naics: NAICSExpertise[];
  top_agencies: AgencyExpertise[];
  business_types: string[];
}

interface RelatedContract {
  award_id: string;
  piid: string;
  awarding_agency_name: string | null;
  awarding_sub_agency_name: string | null;
  naics_code: string | null;
  naics_description: string | null;
  total_obligation: number | null;
  period_of_performance_end: string | null;
  days_until_expiration: number | null;
  pop_state: string | null;
  set_aside_type: string | null;
  usaspending_link: string | null;
}

interface RelatedContractsData {
  incumbent_uei: string;
  incumbent_name: string;
  total_count: number;
  active_contracts: RelatedContract[];
  recently_expired: RelatedContract[];
}

interface MatchedOpportunity {
  opportunity: {
    notice_id: string;
    title: string;
    notice_type: string | null;
    agency_name: string | null;
    naics_code: string | null;
    set_aside_type: string | null;
    posted_date: string | null;
    response_deadline: string | null;
    ui_link: string | null;
  };
  match_score: number;
  match_reasons: string[];
}

interface MatchedOpportunitiesData {
  recompete_id: string;
  recompete_piid: string;
  recompete_naics: string | null;
  recompete_agency: string | null;
  matched_opportunities: MatchedOpportunity[];
  total_matches: number;
}

function formatCurrency(value: number | null): string {
  if (!value) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(dateString: string | null): string {
  if (!dateString) return "N/A";
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function formatShortDate(dateString: string | null): string {
  if (!dateString) return "N/A";
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function DaysBadge({ days }: { days: number | null }) {
  if (days === null) return <span className="text-gray-500">N/A</span>;

  const getColor = () => {
    if (days <= 30) return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
    if (days <= 90) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
    return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
  };

  return (
    <span className={`inline-flex items-center px-3 py-1 text-sm font-medium rounded-full ${getColor()}`}>
      {days} days until expiration
    </span>
  );
}

function SmallDaysBadge({ days }: { days: number | null }) {
  if (days === null) return <span className="text-gray-500 text-xs">N/A</span>;

  const getColor = () => {
    if (days <= 30) return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
    if (days <= 90) return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400";
    if (days < 0) return "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400";
    return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400";
  };

  const label = days < 0 ? `Expired ${Math.abs(days)}d ago` : `${days}d`;

  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded ${getColor()}`}>
      {label}
    </span>
  );
}

// Vulnerability Badge component - shows how beatable the incumbent is
function VulnerabilityBadge({ vulnerability }: { vulnerability: IncumbentVulnerability }) {
  const getColor = () => {
    if (vulnerability.level === "High") return "bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800";
    if (vulnerability.level === "Medium") return "bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400 dark:border-yellow-800";
    return "bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800";
  };

  const getLabel = () => {
    if (vulnerability.level === "High") return "Beatable";
    if (vulnerability.level === "Medium") return "Moderate";
    return "Strong Incumbent";
  };

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium rounded-lg border ${getColor()}`}>
      <span className="text-lg">{vulnerability.level === "High" ? "🎯" : vulnerability.level === "Medium" ? "⚡" : "🛡️"}</span>
      <div>
        <div className="font-semibold">{getLabel()}</div>
        <div className="text-xs opacity-75">Vulnerability: {vulnerability.vulnerability_score}%</div>
      </div>
    </div>
  );
}

// Detailed Vulnerability Card for expanded view
function VulnerabilityCard({ vulnerability }: { vulnerability: IncumbentVulnerability }) {
  const getFactorColor = (score: number) => {
    if (score >= 70) return "text-green-600 dark:text-green-400";
    if (score >= 40) return "text-yellow-600 dark:text-yellow-400";
    return "text-red-600 dark:text-red-400";
  };

  const getBarColor = (score: number) => {
    if (score >= 70) return "bg-green-500";
    if (score >= 40) return "bg-yellow-500";
    return "bg-red-500";
  };

  return (
    <div className="p-4 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex items-center justify-center w-12 h-12 bg-emerald-100 dark:bg-emerald-900/40 rounded-full">
          <span className={`text-xl font-bold ${getFactorColor(vulnerability.vulnerability_score)}`}>
            {vulnerability.vulnerability_score}%
          </span>
        </div>
        <div>
          <div className="font-semibold text-emerald-900 dark:text-emerald-100">
            Incumbent Vulnerability Analysis
          </div>
          <div className="text-sm text-emerald-700 dark:text-emerald-300">
            {vulnerability.recommendation}
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {/* Concentration Risk */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-700 dark:text-gray-300">Concentration Risk</span>
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div className={`h-full ${getBarColor(vulnerability.factors.concentration.score)}`} style={{ width: `${vulnerability.factors.concentration.score}%` }}></div>
            </div>
            <span className={`text-sm font-medium w-8 text-right ${getFactorColor(vulnerability.factors.concentration.score)}`}>
              {vulnerability.factors.concentration.score}
            </span>
          </div>
        </div>

        {/* Expertise */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-700 dark:text-gray-300">NAICS Expertise</span>
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div className={`h-full ${getBarColor(vulnerability.factors.expertise.score)}`} style={{ width: `${vulnerability.factors.expertise.score}%` }}></div>
            </div>
            <span className={`text-sm font-medium w-8 text-right ${getFactorColor(vulnerability.factors.expertise.score)}`}>
              {vulnerability.factors.expertise.score}
            </span>
          </div>
        </div>

        {/* Trajectory */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-700 dark:text-gray-300">Contract Trajectory</span>
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div className={`h-full ${getBarColor(vulnerability.factors.trajectory.score)}`} style={{ width: `${vulnerability.factors.trajectory.score}%` }}></div>
            </div>
            <span className={`text-sm font-medium w-8 text-right ${getFactorColor(vulnerability.factors.trajectory.score)}`}>
              {vulnerability.factors.trajectory.score}
            </span>
          </div>
        </div>

        {/* Market Share */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-700 dark:text-gray-300">Market Share</span>
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div className={`h-full ${getBarColor(vulnerability.factors.market_share.score)}`} style={{ width: `${vulnerability.factors.market_share.score}%` }}></div>
            </div>
            <span className={`text-sm font-medium w-8 text-right ${getFactorColor(vulnerability.factors.market_share.score)}`}>
              {vulnerability.factors.market_share.score}
            </span>
          </div>
        </div>

        {/* Recompete History */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-700 dark:text-gray-300">Recompete History</span>
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div className={`h-full ${getBarColor(vulnerability.factors.recompete_history.score)}`} style={{ width: `${vulnerability.factors.recompete_history.score}%` }}></div>
            </div>
            <span className={`text-sm font-medium w-8 text-right ${getFactorColor(vulnerability.factors.recompete_history.score)}`}>
              {vulnerability.factors.recompete_history.score}
            </span>
          </div>
        </div>
      </div>

      {vulnerability.summary && (
        <div className="mt-4 pt-3 border-t border-emerald-200 dark:border-emerald-700 text-xs text-gray-500">
          {vulnerability.incumbent_name}: {vulnerability.summary.total_contracts} contracts worth ${(vulnerability.summary.total_value / 1000000).toFixed(1)}M
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex flex-col sm:flex-row sm:justify-between py-3 border-b border-gray-100 dark:border-gray-700">
      <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">{label}</dt>
      <dd className="mt-1 sm:mt-0 text-sm text-gray-900 dark:text-white">{value || "N/A"}</dd>
    </div>
  );
}

function MatchScoreBadge({ score }: { score: number }) {
  const getColor = () => {
    if (score >= 80) return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
    if (score >= 60) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
    return "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300";
  };

  return (
    <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded ${getColor()}`}>
      {score}% match
    </span>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-8">
      <div className="w-6 h-6 border-2 border-blue-500 rounded-full animate-spin border-t-transparent"></div>
    </div>
  );
}

// Collapsible Section Component
function CollapsibleSection({
  title,
  icon,
  isOpen,
  onToggle,
  badge,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  isOpen: boolean;
  onToggle: () => void;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg shadow-sm dark:bg-gray-800 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-gray-500 dark:text-gray-400">{icon}</span>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
          {badge}
        </div>
        <svg
          className={`w-5 h-5 text-gray-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isOpen && <div className="px-6 pb-6 border-t border-gray-100 dark:border-gray-700">{children}</div>}
    </div>
  );
}

// Contract History Section
function ContractHistorySection({ recompeteId }: { recompeteId: string }) {
  const [data, setData] = useState<ContractHistoryData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(
          `${import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1"}/public/recompetes/${recompeteId}/contract-history`
        );
        const result = await response.json();
        if (result.error) throw new Error(result.error);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [recompeteId]);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <div className="py-4 text-red-500 text-sm">{error}</div>;
  if (!data || data.contract_history.length === 0) {
    return <div className="py-4 text-gray-500 text-sm">No contract history found.</div>;
  }

  return (
    <div className="pt-4 space-y-4">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <div className="text-xs text-gray-500 dark:text-gray-400">Total Contracts</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-white">{data.total_contracts}</div>
        </div>
        <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <div className="text-xs text-gray-500 dark:text-gray-400">Total Obligated</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-white">{formatCurrency(data.total_obligated)}</div>
        </div>
        <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <div className="text-xs text-gray-500 dark:text-gray-400">Base PIID</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-white font-mono">{data.base_piid}</div>
        </div>
      </div>

      {/* Contract Timeline */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Award Timeline</h3>
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {data.contract_history.map((contract, idx) => (
            <div
              key={contract.award_id}
              className={`p-3 rounded-lg border ${
                idx === 0 ? "border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20" : "border-gray-200 dark:border-gray-700"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-medium text-gray-900 dark:text-white">{contract.piid}</span>
                    {idx === 0 && (
                      <span className="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 dark:bg-blue-800 dark:text-blue-200 rounded">
                        Current
                      </span>
                    )}
                  </div>
                  <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {contract.award_type_description || contract.award_type} • {formatShortDate(contract.award_date)}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium text-gray-900 dark:text-white">
                    {formatCurrency(contract.total_obligation)}
                  </div>
                  {contract.usaspending_link && (
                    <a
                      href={contract.usaspending_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:underline"
                    >
                      View
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Incumbent Profile Section
function IncumbentProfileSection({ recompeteId }: { recompeteId: string }) {
  const [data, setData] = useState<IncumbentProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(
          `${import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1"}/public/recompetes/${recompeteId}/incumbent-profile`
        );
        const result = await response.json();
        if (result.error) throw new Error(result.error);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [recompeteId]);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <div className="py-4 text-red-500 text-sm">{error}</div>;
  if (!data) return <div className="py-4 text-gray-500 text-sm">No incumbent profile available.</div>;

  return (
    <div className="pt-4 space-y-6">
      {/* Company Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Company Info</h3>
          <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-2">
            <div>
              <div className="text-lg font-semibold text-gray-900 dark:text-white">{data.name}</div>
              <div className="text-xs text-gray-500 dark:text-gray-400 font-mono">UEI: {data.uei}</div>
            </div>
            {data.location && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {[data.location.city, data.location.state, data.location.zip].filter(Boolean).join(", ")}
              </div>
            )}
            {data.parent_company?.name && (
              <div className="text-sm text-gray-500 dark:text-gray-400">
                Parent: {data.parent_company.name}
              </div>
            )}
            {data.business_types.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {data.business_types.slice(0, 5).map((bt, idx) => (
                  <span key={idx} className="px-2 py-0.5 text-xs bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 rounded">
                    {bt}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div>
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Statistics</h3>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <div className="text-xs text-gray-500 dark:text-gray-400">Total Awards</div>
              <div className="text-lg font-semibold text-gray-900 dark:text-white">{data.statistics.total_awards}</div>
            </div>
            <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <div className="text-xs text-gray-500 dark:text-gray-400">Total Value</div>
              <div className="text-lg font-semibold text-gray-900 dark:text-white">{formatCurrency(data.statistics.total_obligation)}</div>
            </div>
            <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <div className="text-xs text-gray-500 dark:text-gray-400">Avg Award</div>
              <div className="text-lg font-semibold text-gray-900 dark:text-white">{formatCurrency(data.statistics.average_award_value)}</div>
            </div>
            <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <div className="text-xs text-gray-500 dark:text-gray-400">Active Since</div>
              <div className="text-sm font-semibold text-gray-900 dark:text-white">{formatShortDate(data.statistics.first_award_date)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* NAICS Expertise */}
      {data.primary_naics.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">NAICS Expertise</h3>
          <div className="space-y-2">
            {data.primary_naics.slice(0, 5).map((naics) => (
              <div key={naics.code} className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700/50 rounded">
                <div className="flex-1 min-w-0">
                  <span className="font-mono text-sm text-gray-900 dark:text-white">{naics.code}</span>
                  <span className="ml-2 text-xs text-gray-500 dark:text-gray-400 truncate">{naics.description}</span>
                </div>
                <div className="text-right">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">{naics.count} awards</span>
                  <span className="ml-2 text-xs text-gray-500">{formatCurrency(naics.total_value)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Agencies */}
      {data.top_agencies.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Top Agencies</h3>
          <div className="space-y-2">
            {data.top_agencies.slice(0, 5).map((agency, idx) => (
              <div key={idx} className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700/50 rounded">
                <div className="flex-1 min-w-0 text-sm text-gray-900 dark:text-white truncate">{agency.agency}</div>
                <div className="text-right">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">{agency.count} awards</span>
                  <span className="ml-2 text-xs text-gray-500">{formatCurrency(agency.total_value)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Related Contracts Section
function RelatedContractsSection({ recompeteId }: { recompeteId: string }) {
  const [data, setData] = useState<RelatedContractsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(
          `${import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1"}/public/recompetes/${recompeteId}/related-contracts`
        );
        const result = await response.json();
        if (result.error) throw new Error(result.error);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [recompeteId]);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <div className="py-4 text-red-500 text-sm">{error}</div>;
  if (!data || (data.active_contracts.length === 0 && data.recently_expired.length === 0)) {
    return <div className="py-4 text-gray-500 text-sm">No related contracts found.</div>;
  }

  const renderContract = (contract: RelatedContract) => (
    <div key={contract.award_id} className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-medium text-gray-900 dark:text-white">{contract.piid}</span>
            <SmallDaysBadge days={contract.days_until_expiration} />
          </div>
          <div className="mt-1 text-xs text-gray-500 dark:text-gray-400 truncate">
            {contract.awarding_agency_name}
          </div>
          <div className="mt-1 flex items-center gap-2">
            {contract.naics_code && (
              <span className="text-xs text-gray-500">{contract.naics_code}</span>
            )}
            {contract.set_aside_type && (
              <span className="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 rounded">
                {contract.set_aside_type}
              </span>
            )}
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm font-medium text-gray-900 dark:text-white">
            {formatCurrency(contract.total_obligation)}
          </div>
          {contract.usaspending_link && (
            <a
              href={contract.usaspending_link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-600 hover:underline"
            >
              View
            </a>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="pt-4 space-y-4">
      <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
        <span className="text-sm text-gray-600 dark:text-gray-400">
          {data.incumbent_name} holds <strong className="text-gray-900 dark:text-white">{data.total_count}</strong> other contracts
        </span>
      </div>

      {data.active_contracts.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full"></span>
            Active Contracts ({data.active_contracts.length})
          </h3>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {data.active_contracts.map(renderContract)}
          </div>
        </div>
      )}

      {data.recently_expired.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
            <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
            Recently Expired ({data.recently_expired.length})
          </h3>
          <div className="space-y-2">
            {data.recently_expired.map(renderContract)}
          </div>
        </div>
      )}
    </div>
  );
}

// Matched Opportunities Section
function MatchedOpportunitiesSection({ recompeteId }: { recompeteId: string }) {
  const [data, setData] = useState<MatchedOpportunitiesData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(
          `${import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1"}/public/recompetes/${recompeteId}/matched-opportunities`
        );
        const result = await response.json();
        if (result.error) throw new Error(result.error);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [recompeteId]);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <div className="py-4 text-red-500 text-sm">{error}</div>;
  if (!data || data.matched_opportunities.length === 0) {
    return (
      <div className="py-4">
        <div className="text-gray-500 text-sm">No matching opportunities found on SAM.gov yet.</div>
        <div className="mt-2 text-xs text-gray-400">
          We're looking for solicitations with NAICS {data?.recompete_naics} from {data?.recompete_agency}
        </div>
      </div>
    );
  }

  return (
    <div className="pt-4 space-y-3">
      <div className="text-sm text-gray-600 dark:text-gray-400">
        Found <strong className="text-gray-900 dark:text-white">{data.total_matches}</strong> potential matches
      </div>

      <div className="space-y-3">
        {data.matched_opportunities.map((match) => (
          <div
            key={match.opportunity.notice_id}
            className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-blue-300 dark:hover:border-blue-600 transition-colors"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <MatchScoreBadge score={match.match_score} />
                  {match.opportunity.notice_type && (
                    <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 rounded">
                      {match.opportunity.notice_type}
                    </span>
                  )}
                </div>
                <h4 className="mt-2 text-sm font-medium text-gray-900 dark:text-white line-clamp-2">
                  {match.opportunity.title}
                </h4>
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  {match.opportunity.agency_name}
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {match.match_reasons.map((reason, idx) => (
                    <span key={idx} className="px-1.5 py-0.5 text-xs bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded">
                      {reason}
                    </span>
                  ))}
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Posted: {formatShortDate(match.opportunity.posted_date)}
                </div>
                {match.opportunity.response_deadline && (
                  <div className="text-xs text-orange-600 dark:text-orange-400">
                    Due: {formatShortDate(match.opportunity.response_deadline)}
                  </div>
                )}
                {match.opportunity.ui_link && (
                  <a
                    href={match.opportunity.ui_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 inline-flex items-center text-xs text-blue-600 hover:underline"
                  >
                    View on SAM.gov
                    <svg className="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function RecompeteDetail() {
  const { id } = useParams<{ id: string }>();
  const [recompete, setRecompete] = useState<RecompeteData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [vulnerability, setVulnerability] = useState<IncumbentVulnerability | null>(null);

  // Enrichment section states
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    history: false,
    incumbent: false,
    related: false,
    matched: true, // Open by default - most actionable
    vulnerability: false,
  });

  const toggleSection = (section: string) => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  useEffect(() => {
    const fetchRecompete = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `${import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1"}/public/recompetes/${id}`
        );

        if (!response.ok) {
          throw new Error("Failed to fetch recompete details");
        }

        const data = await response.json();
        if (data.error) {
          throw new Error(data.error);
        }
        setRecompete(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load recompete");
      } finally {
        setIsLoading(false);
      }
    };

    if (id) {
      fetchRecompete();
    }
  }, [id]);

  // Fetch incumbent vulnerability when recompete loads
  useEffect(() => {
    const fetchVulnerability = async () => {
      if (!recompete?.incumbent_uei) return;

      try {
        const vulnData = await getIncumbentVulnerability(
          recompete.incumbent_uei,
          recompete.naics_code || undefined,
          recompete.awarding_agency_name || undefined
        );
        setVulnerability(vulnData);
      } catch (err) {
        // Silently fail - vulnerability is optional
        console.debug("Could not fetch incumbent vulnerability:", err);
      }
    };

    fetchVulnerability();
  }, [recompete?.incumbent_uei, recompete?.naics_code, recompete?.awarding_agency_name]);

  if (isLoading) {
    return (
      <>
        <PageMeta title="Loading... | BidKing" description="Loading recompete details" />
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-blue-500 rounded-full animate-spin border-t-transparent"></div>
        </div>
      </>
    );
  }

  if (error || !recompete) {
    return (
      <>
        <PageMeta title="Error | BidKing" description="Error loading recompete" />
        <div className="p-4 text-red-600 bg-red-50 rounded-lg dark:bg-red-900/20 dark:text-red-400">
          {error || "Recompete not found"}
        </div>
        <Link to="/recompetes" className="mt-4 inline-block text-blue-600 hover:underline">
          ← Back to Recompetes
        </Link>
      </>
    );
  }

  const details = recompete.contract_details;

  return (
    <>
      <PageMeta
        title={`${recompete.piid} | Recompete | BidKing`}
        description={`Contract ${recompete.piid} expiring ${formatDate(recompete.period_of_performance_end)}`}
      />
      <PageBreadcrumb pageTitle="Recompete Details" />

      <div className="space-y-6">
        {/* Back link */}
        <Link to="/recompetes" className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Recompetes
        </Link>

        {/* Header Card */}
        <div className="p-6 bg-white rounded-lg shadow-sm dark:bg-gray-800">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                {recompete.piid}
              </h1>
              <p className="mt-1 text-gray-500 dark:text-gray-400">
                {recompete.awarding_agency_name}
              </p>
              <div className="mt-3 flex flex-wrap gap-3 items-center">
                <DaysBadge days={recompete.days_until_expiration} />
                {vulnerability && <VulnerabilityBadge vulnerability={vulnerability} />}
              </div>
            </div>
            <div className="flex flex-col sm:flex-row gap-3">
              {recompete.usaspending_link && (
                <a
                  href={recompete.usaspending_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                >
                  View on USAspending
                  <svg className="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              )}
              {recompete.linked_opportunity_id && (
                <a
                  href={`https://sam.gov/opp/${recompete.linked_opportunity_id}/view`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700"
                >
                  View on SAM.gov
                  <svg className="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Key Information */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Contract Overview */}
          <div className="p-6 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Contract Overview
            </h2>
            <dl className="space-y-0">
              <InfoRow label="Contract Number (PIID)" value={recompete.piid} />
              <InfoRow label="Award ID" value={recompete.award_id} />
              <InfoRow label="Expiration Date" value={formatDate(recompete.period_of_performance_end)} />
              <InfoRow label="Contract Value" value={formatCurrency(recompete.total_value)} />
              <InfoRow label="NAICS Code" value={recompete.naics_code} />
              <InfoRow label="NAICS Description" value={details?.naics_description} />
              <InfoRow label="PSC Code" value={details?.psc_code} />
              <InfoRow label="Status" value={recompete.status} />
            </dl>
          </div>

          {/* Incumbent Information */}
          <div className="p-6 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Current Incumbent
            </h2>
            <dl className="space-y-0">
              <InfoRow label="Company Name" value={recompete.incumbent_name} />
              <InfoRow label="UEI" value={recompete.incumbent_uei} />
              <InfoRow label="City" value={details?.recipient_city} />
              <InfoRow label="State" value={details?.recipient_state} />
            </dl>
          </div>
        </div>

        {/* Agency Information */}
        <div className="p-6 bg-white rounded-lg shadow-sm dark:bg-gray-800">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Agency Information
          </h2>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
            <InfoRow label="Agency" value={recompete.awarding_agency_name} />
            <InfoRow label="Sub-Agency" value={details?.awarding_sub_agency_name} />
            <InfoRow label="Office" value={details?.awarding_office_name} />
          </dl>
        </div>

        {/* Contract Details */}
        {details && (
          <div className="p-6 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Contract Details
            </h2>
            <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
              <InfoRow label="Award Type" value={details.award_type_description || details.award_type} />
              <InfoRow label="Award Date" value={formatDate(details.award_date)} />
              <InfoRow label="Period of Performance Start" value={formatDate(details.period_of_performance_start)} />
              <InfoRow label="Total Obligation" value={formatCurrency(details.total_obligation)} />
              <InfoRow label="Base + All Options" value={formatCurrency(details.base_and_all_options_value)} />
              <InfoRow label="Competition Type" value={details.competition_type} />
              <InfoRow label="Number of Offers" value={details.number_of_offers?.toString()} />
              <InfoRow label="Set-Aside Type" value={details.set_aside_type} />
            </dl>
          </div>
        )}

        {/* Place of Performance */}
        {details && (details.pop_city || details.pop_state) && (
          <div className="p-6 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Place of Performance
            </h2>
            <dl className="grid grid-cols-1 md:grid-cols-3 gap-x-8">
              <InfoRow label="City" value={details.pop_city} />
              <InfoRow label="State" value={details.pop_state} />
              <InfoRow label="ZIP Code" value={details.pop_zip} />
            </dl>
          </div>
        )}

        {/* ============== ENRICHMENT SECTIONS ============== */}

        {/* Matched Opportunities - Most actionable, open by default */}
        <CollapsibleSection
          title="Matched SAM.gov Opportunities"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
          isOpen={openSections.matched}
          onToggle={() => toggleSection("matched")}
          badge={
            <span className="px-2 py-0.5 text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded-full">
              New
            </span>
          }
        >
          {openSections.matched && <MatchedOpportunitiesSection recompeteId={id!} />}
        </CollapsibleSection>

        {/* Incumbent Vulnerability Analysis */}
        {vulnerability && (
          <CollapsibleSection
            title="Incumbent Vulnerability Analysis"
            icon={
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            }
            isOpen={openSections.vulnerability}
            onToggle={() => toggleSection("vulnerability")}
            badge={
              <span className={`px-2 py-0.5 text-xs rounded-full ${
                vulnerability.level === "High" ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" :
                vulnerability.level === "Medium" ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400" :
                "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
              }`}>
                {vulnerability.level === "High" ? "Beatable" : vulnerability.level === "Medium" ? "Moderate" : "Strong"}
              </span>
            }
          >
            {openSections.vulnerability && <VulnerabilityCard vulnerability={vulnerability} />}
          </CollapsibleSection>
        )}

        {/* Incumbent Profile */}
        <CollapsibleSection
          title="Incumbent Profile"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          }
          isOpen={openSections.incumbent}
          onToggle={() => toggleSection("incumbent")}
        >
          {openSections.incumbent && <IncumbentProfileSection recompeteId={id!} />}
        </CollapsibleSection>

        {/* Related Contracts */}
        <CollapsibleSection
          title="Incumbent's Other Contracts"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          }
          isOpen={openSections.related}
          onToggle={() => toggleSection("related")}
        >
          {openSections.related && <RelatedContractsSection recompeteId={id!} />}
        </CollapsibleSection>

        {/* Contract History */}
        <CollapsibleSection
          title="Contract History & Value Trends"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          }
          isOpen={openSections.history}
          onToggle={() => toggleSection("history")}
        >
          {openSections.history && <ContractHistorySection recompeteId={id!} />}
        </CollapsibleSection>

        {/* Tip Banner */}
        <div className="p-4 bg-blue-50 rounded-lg dark:bg-blue-900/20">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-medium text-blue-800 dark:text-blue-300">
                Pursuing This Recompete?
              </h3>
              <p className="mt-1 text-sm text-blue-700 dark:text-blue-400">
                When this contract expires, the government will likely issue a new solicitation on SAM.gov.
                Set up an alert profile with this NAICS code ({recompete.naics_code}) and agency to be notified
                when the new opportunity is posted.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
