import { useEffect, useState } from "react";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";

// Types for analytics data
interface MarketOverview {
  contracts: {
    total_awards: number;
    total_value: number;
    average_value: number;
    min_value: number;
    max_value: number;
  };
  recompetes: {
    total_upcoming: number;
    total_value: number;
    average_value: number;
    expiring_30_days: number;
    expiring_90_days: number;
    expiring_365_days: number;
  };
  diversity: {
    unique_agencies: number;
    unique_naics_codes: number;
  };
}

interface ValueDistribution {
  distribution: {
    range: string;
    count: number;
    total_value: number;
  }[];
}

interface NAICSData {
  by_naics: {
    naics_code: string;
    naics_description: string;
    contract_count: number;
    total_value: number;
    average_value: number;
  }[];
}

interface AgencyData {
  by_agency: {
    agency_name: string;
    contract_count: number;
    total_value: number;
    average_value: number;
  }[];
}

interface IncumbentData {
  top_incumbents: {
    incumbent_name: string;
    contract_count: number;
    total_value: number;
    average_value: number;
  }[];
}

// Format currency
function formatCurrency(value: number): string {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

// Format large numbers
function formatNumber(value: number): string {
  return value.toLocaleString();
}

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [distribution, setDistribution] = useState<ValueDistribution | null>(null);
  const [naicsData, setNaicsData] = useState<NAICSData | null>(null);
  const [agencyData, setAgencyData] = useState<AgencyData | null>(null);
  const [incumbentData, setIncumbentData] = useState<IncumbentData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const API_URL = import.meta.env.VITE_API_URL || "https://api.bidking.ai/api/v1";

  useEffect(() => {
    const fetchAnalytics = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const [overviewRes, distRes, naicsRes, agencyRes, incumbentRes] = await Promise.all([
          fetch(`${API_URL}/analytics/market-overview`),
          fetch(`${API_URL}/analytics/value-distribution`),
          fetch(`${API_URL}/analytics/by-naics?limit=10`),
          fetch(`${API_URL}/analytics/by-agency?limit=10`),
          fetch(`${API_URL}/analytics/top-incumbents?limit=10`),
        ]);

        if (!overviewRes.ok || !distRes.ok || !naicsRes.ok || !agencyRes.ok || !incumbentRes.ok) {
          throw new Error("Failed to fetch analytics data");
        }

        const [overviewData, distData, naicsDataRes, agencyDataRes, incumbentDataRes] = await Promise.all([
          overviewRes.json(),
          distRes.json(),
          naicsRes.json(),
          agencyRes.json(),
          incumbentRes.json(),
        ]);

        setOverview(overviewData);
        setDistribution(distData);
        setNaicsData(naicsDataRes);
        setAgencyData(agencyDataRes);
        setIncumbentData(incumbentDataRes);
      } catch (err) {
        console.error("Analytics fetch error:", err);
        setError("Failed to load analytics data");
      } finally {
        setIsLoading(false);
      }
    };

    fetchAnalytics();
  }, [API_URL]);

  if (isLoading) {
    return (
      <>
        <PageMeta title="Analytics | BidKing" description="Federal contract market analytics" />
        <PageBreadcrumb pageTitle="Analytics" />
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-blue-500 rounded-full animate-spin border-t-transparent"></div>
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <PageMeta title="Analytics | BidKing" description="Federal contract market analytics" />
        <PageBreadcrumb pageTitle="Analytics" />
        <div className="p-4 text-red-600 bg-red-50 rounded-lg dark:bg-red-900/20">{error}</div>
      </>
    );
  }

  // Calculate max for distribution chart
  const maxDistCount = Math.max(...(distribution?.distribution.map((d) => d.count) || [1]));

  return (
    <>
      <PageMeta title="Analytics | BidKing" description="Federal contract market analytics" />
      <PageBreadcrumb pageTitle="Analytics" />

      <div className="space-y-6">
        {/* Market Overview Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <p className="text-sm text-gray-500 dark:text-gray-400">Expiring Contracts</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {formatNumber(overview?.recompetes.total_upcoming || 0)}
            </p>
            <p className="text-xs text-gray-400">Next 12 months</p>
          </div>
          <div className="p-4 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <p className="text-sm text-gray-500 dark:text-gray-400">Total Value</p>
            <p className="text-2xl font-bold text-green-600">
              {formatCurrency(overview?.recompetes.total_value || 0)}
            </p>
            <p className="text-xs text-gray-400">Recompete opportunities</p>
          </div>
          <div className="p-4 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <p className="text-sm text-gray-500 dark:text-gray-400">Avg Contract</p>
            <p className="text-2xl font-bold text-blue-600">
              {formatCurrency(overview?.recompetes.average_value || 0)}
            </p>
            <p className="text-xs text-gray-400">Per contract</p>
          </div>
          <div className="p-4 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <p className="text-sm text-gray-500 dark:text-gray-400">Expiring Soon</p>
            <p className="text-2xl font-bold text-red-600">
              {formatNumber(overview?.recompetes.expiring_30_days || 0)}
            </p>
            <p className="text-xs text-gray-400">Next 30 days</p>
          </div>
        </div>

        {/* Quick Stats Row */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-center">
            <p className="text-lg font-bold text-yellow-700 dark:text-yellow-400">
              {formatNumber(overview?.recompetes.expiring_90_days || 0)}
            </p>
            <p className="text-xs text-yellow-600 dark:text-yellow-500">Expiring in 90 days</p>
          </div>
          <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-center">
            <p className="text-lg font-bold text-blue-700 dark:text-blue-400">
              {overview?.diversity.unique_agencies || 0}
            </p>
            <p className="text-xs text-blue-600 dark:text-blue-500">Agencies</p>
          </div>
          <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg text-center">
            <p className="text-lg font-bold text-purple-700 dark:text-purple-400">
              {overview?.diversity.unique_naics_codes || 0}
            </p>
            <p className="text-xs text-purple-600 dark:text-purple-500">NAICS Codes</p>
          </div>
        </div>

        {/* Value Distribution Chart */}
        <div className="bg-white rounded-lg shadow-sm p-6 dark:bg-gray-800">
          <h2 className="text-lg font-semibold mb-4 dark:text-white">Contract Value Distribution</h2>
          <div className="space-y-3">
            {distribution?.distribution.map((bucket) => (
              <div key={bucket.range} className="flex items-center gap-4">
                <div className="w-32 text-sm text-gray-600 dark:text-gray-400 text-right">
                  {bucket.range}
                </div>
                <div className="flex-1 h-8 bg-gray-100 dark:bg-gray-700 rounded overflow-hidden">
                  <div
                    className="h-full bg-blue-500 dark:bg-blue-600 flex items-center px-2"
                    style={{ width: `${(bucket.count / maxDistCount) * 100}%` }}
                  >
                    <span className="text-xs text-white font-medium">
                      {bucket.count > 0 ? bucket.count : ""}
                    </span>
                  </div>
                </div>
                <div className="w-24 text-sm text-gray-500 dark:text-gray-400">
                  {formatCurrency(bucket.total_value)}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="grid md:grid-cols-2 gap-6">
          {/* NAICS Leaderboard */}
          <div className="bg-white rounded-lg shadow-sm p-6 dark:bg-gray-800">
            <h2 className="text-lg font-semibold mb-4 dark:text-white">Top NAICS Codes</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b dark:border-gray-700">
                    <th className="text-left py-2 px-2 text-gray-500 font-medium">NAICS</th>
                    <th className="text-right py-2 px-2 text-gray-500 font-medium">Contracts</th>
                    <th className="text-right py-2 px-2 text-gray-500 font-medium">Total Value</th>
                  </tr>
                </thead>
                <tbody>
                  {naicsData?.by_naics.map((row, idx) => (
                    <tr
                      key={row.naics_code}
                      className={`border-b dark:border-gray-700 ${idx < 3 ? "bg-blue-50/50 dark:bg-blue-900/10" : ""}`}
                    >
                      <td className="py-2 px-2">
                        <div className="font-medium text-gray-900 dark:text-white">{row.naics_code}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                          {row.naics_description}
                        </div>
                      </td>
                      <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-300">
                        {formatNumber(row.contract_count)}
                      </td>
                      <td className="py-2 px-2 text-right font-medium text-green-600">
                        {formatCurrency(row.total_value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Agency Leaderboard */}
          <div className="bg-white rounded-lg shadow-sm p-6 dark:bg-gray-800">
            <h2 className="text-lg font-semibold mb-4 dark:text-white">Top Agencies</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b dark:border-gray-700">
                    <th className="text-left py-2 px-2 text-gray-500 font-medium">Agency</th>
                    <th className="text-right py-2 px-2 text-gray-500 font-medium">Contracts</th>
                    <th className="text-right py-2 px-2 text-gray-500 font-medium">Total Value</th>
                  </tr>
                </thead>
                <tbody>
                  {agencyData?.by_agency.map((row, idx) => (
                    <tr
                      key={row.agency_name}
                      className={`border-b dark:border-gray-700 ${idx < 3 ? "bg-blue-50/50 dark:bg-blue-900/10" : ""}`}
                    >
                      <td className="py-2 px-2">
                        <div className="font-medium text-gray-900 dark:text-white truncate max-w-[200px]">
                          {row.agency_name}
                        </div>
                      </td>
                      <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-300">
                        {formatNumber(row.contract_count)}
                      </td>
                      <td className="py-2 px-2 text-right font-medium text-green-600">
                        {formatCurrency(row.total_value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Top Incumbents */}
        <div className="bg-white rounded-lg shadow-sm p-6 dark:bg-gray-800">
          <h2 className="text-lg font-semibold mb-4 dark:text-white">Top Incumbents (Contracts Expiring)</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Companies with the most contracts expiring in the next 12 months
          </p>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b dark:border-gray-700">
                  <th className="text-left py-2 px-3 text-gray-500 font-medium">Incumbent</th>
                  <th className="text-right py-2 px-3 text-gray-500 font-medium">Contracts</th>
                  <th className="text-right py-2 px-3 text-gray-500 font-medium">Total Value</th>
                  <th className="text-right py-2 px-3 text-gray-500 font-medium">Avg Contract</th>
                </tr>
              </thead>
              <tbody>
                {incumbentData?.top_incumbents.map((row, idx) => (
                  <tr
                    key={row.incumbent_name}
                    className={`border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 ${
                      idx < 3 ? "bg-yellow-50/50 dark:bg-yellow-900/10" : ""
                    }`}
                  >
                    <td className="py-3 px-3">
                      <div className="font-medium text-gray-900 dark:text-white">{row.incumbent_name}</div>
                    </td>
                    <td className="py-3 px-3 text-right text-gray-600 dark:text-gray-300">
                      {formatNumber(row.contract_count)}
                    </td>
                    <td className="py-3 px-3 text-right font-medium text-green-600">
                      {formatCurrency(row.total_value)}
                    </td>
                    <td className="py-3 px-3 text-right text-gray-500 dark:text-gray-400">
                      {formatCurrency(row.average_value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}
