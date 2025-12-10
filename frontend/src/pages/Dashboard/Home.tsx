import { useEffect } from "react";
import { Link } from "react-router";
import PageMeta from "../../components/common/PageMeta";
import { useOpportunitiesStore } from "../../stores/opportunitiesStore";
import { useAlertsStore } from "../../stores/alertsStore";

// Stat card component
function StatCard({
  title,
  value,
  icon,
  trend,
  trendUp
}: {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: string;
  trendUp?: boolean;
}) {
  return (
    <div className="p-6 bg-white rounded-xl shadow-sm dark:bg-gray-800">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
          <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{value}</p>
          {trend && (
            <p className={`mt-2 text-sm ${trendUp ? 'text-green-600' : 'text-red-600'}`}>
              {trendUp ? '↑' : '↓'} {trend}
            </p>
          )}
        </div>
        <div className="p-3 bg-blue-100 rounded-xl dark:bg-blue-900/30">
          {icon}
        </div>
      </div>
    </div>
  );
}

// Quick action card
function QuickAction({
  title,
  description,
  to,
  icon
}: {
  title: string;
  description: string;
  to: string;
  icon: React.ReactNode;
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-4 p-4 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow dark:bg-gray-800 group"
    >
      <div className="p-3 bg-gray-100 rounded-xl group-hover:bg-blue-100 transition-colors dark:bg-gray-700 dark:group-hover:bg-blue-900/30">
        {icon}
      </div>
      <div>
        <h3 className="font-semibold text-gray-900 dark:text-white">{title}</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">{description}</p>
      </div>
    </Link>
  );
}

// Format date helper
function formatDate(dateString: string | null): string {
  if (!dateString) return "N/A";
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

// Days until deadline
function getDaysUntil(dateString: string | null): { text: string; urgent: boolean } {
  if (!dateString) return { text: "", urgent: false };
  const now = new Date();
  const deadline = new Date(dateString);
  const diffTime = deadline.getTime() - now.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return { text: "Expired", urgent: true };
  if (diffDays === 0) return { text: "Today!", urgent: true };
  if (diffDays === 1) return { text: "Tomorrow", urgent: true };
  if (diffDays <= 7) return { text: `${diffDays} days`, urgent: true };
  return { text: `${diffDays} days`, urgent: false };
}

export default function Home() {
  const { opportunities, total, fetchOpportunities, isLoading: oppsLoading } = useOpportunitiesStore();
  const { alertProfiles, fetchAlertProfiles } = useAlertsStore();

  useEffect(() => {
    fetchOpportunities();
    fetchAlertProfiles();
  }, []);

  // Get high-score opportunities
  const highScoreOpps = opportunities.filter(opp => opp.likelihood_score >= 70).slice(0, 5);

  // Get upcoming deadlines
  const upcomingDeadlines = opportunities
    .filter(opp => opp.response_deadline)
    .sort((a, b) => new Date(a.response_deadline!).getTime() - new Date(b.response_deadline!).getTime())
    .slice(0, 5);

  // Active alert profiles
  const activeProfiles = alertProfiles.filter(p => p.is_active).length;

  return (
    <>
      <PageMeta
        title="Dashboard | BidKing"
        description="Your federal contract opportunity dashboard"
      />

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Welcome back!
        </h1>
        <p className="mt-1 text-gray-500 dark:text-gray-400">
          Here's what's happening with your federal contract opportunities.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-6 mb-8 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Opportunities"
          value={total}
          icon={
            <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          }
        />
        <StatCard
          title="High Score (70+)"
          value={opportunities.filter(o => o.likelihood_score >= 70).length}
          icon={
            <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          }
        />
        <StatCard
          title="Active Alerts"
          value={activeProfiles}
          icon={
            <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
          }
        />
        <StatCard
          title="Saved Opportunities"
          value={0}
          icon={
            <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
            </svg>
          }
        />
      </div>

      {/* Quick Actions */}
      <div className="mb-8">
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Quick Actions</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <QuickAction
            title="Browse Opportunities"
            description="Search and filter federal contracts"
            to="/opportunities"
            icon={
              <svg className="w-6 h-6 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            }
          />
          <QuickAction
            title="Create Alert Profile"
            description="Set up custom notifications"
            to="/alerts/create"
            icon={
              <svg className="w-6 h-6 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
            }
          />
          <QuickAction
            title="Manage Alerts"
            description="View and edit your alert profiles"
            to="/alerts"
            icon={
              <svg className="w-6 h-6 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            }
          />
        </div>
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* High Score Opportunities */}
        <div className="p-6 bg-white rounded-xl shadow-sm dark:bg-gray-800">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Top Opportunities
            </h2>
            <Link to="/opportunities?min_score=70" className="text-sm text-blue-600 hover:text-blue-700">
              View all →
            </Link>
          </div>
          {oppsLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-6 h-6 border-2 border-blue-500 rounded-full animate-spin border-t-transparent"></div>
            </div>
          ) : highScoreOpps.length === 0 ? (
            <p className="py-8 text-center text-gray-500 dark:text-gray-400">
              No high-score opportunities yet. Check back soon!
            </p>
          ) : (
            <div className="space-y-3">
              {highScoreOpps.map((opp) => (
                <Link
                  key={opp.id}
                  to={`/opportunities/${opp.id}`}
                  className="block p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 truncate dark:text-white">
                        {opp.title}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {opp.agency_name || "Unknown Agency"}
                      </p>
                    </div>
                    <span className="inline-flex items-center px-2 py-1 text-xs font-semibold text-green-800 bg-green-100 rounded dark:bg-green-900/30 dark:text-green-400">
                      {opp.likelihood_score}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Upcoming Deadlines */}
        <div className="p-6 bg-white rounded-xl shadow-sm dark:bg-gray-800">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Upcoming Deadlines
            </h2>
            <Link to="/opportunities" className="text-sm text-blue-600 hover:text-blue-700">
              View all →
            </Link>
          </div>
          {oppsLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-6 h-6 border-2 border-blue-500 rounded-full animate-spin border-t-transparent"></div>
            </div>
          ) : upcomingDeadlines.length === 0 ? (
            <p className="py-8 text-center text-gray-500 dark:text-gray-400">
              No upcoming deadlines found.
            </p>
          ) : (
            <div className="space-y-3">
              {upcomingDeadlines.map((opp) => {
                const deadline = getDaysUntil(opp.response_deadline);
                return (
                  <Link
                    key={opp.id}
                    to={`/opportunities/${opp.id}`}
                    className="block p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate dark:text-white">
                          {opp.title}
                        </p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          Due: {formatDate(opp.response_deadline)}
                        </p>
                      </div>
                      <span className={`inline-flex items-center px-2 py-1 text-xs font-semibold rounded ${
                        deadline.urgent
                          ? 'text-red-800 bg-red-100 dark:bg-red-900/30 dark:text-red-400'
                          : 'text-gray-800 bg-gray-100 dark:bg-gray-700 dark:text-gray-300'
                      }`}>
                        {deadline.text}
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Alert Profiles Summary */}
      {alertProfiles.length > 0 && (
        <div className="mt-6 p-6 bg-white rounded-xl shadow-sm dark:bg-gray-800">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Your Alert Profiles
            </h2>
            <Link to="/alerts" className="text-sm text-blue-600 hover:text-blue-700">
              Manage →
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {alertProfiles.slice(0, 3).map((profile) => (
              <div
                key={profile.id}
                className={`p-4 rounded-lg border ${
                  profile.is_active
                    ? 'border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/20'
                    : 'border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-700/50'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium text-gray-900 dark:text-white">{profile.name}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    profile.is_active
                      ? 'bg-green-200 text-green-800 dark:bg-green-800 dark:text-green-200'
                      : 'bg-gray-200 text-gray-600 dark:bg-gray-600 dark:text-gray-300'
                  }`}>
                    {profile.is_active ? 'Active' : 'Paused'}
                  </span>
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {profile.match_count} matches • {profile.alert_frequency}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
