import { useState, useEffect } from "react";
import { Link } from "react-router";
import { useAuthStore } from "../stores/authStore";
import { subscriptionsApi } from "../api/subscriptions";
import { Usage } from "../types";

export default function SidebarWidget() {
  const { user } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);
  const [usage, setUsage] = useState<Usage | null>(null);
  const tier = user?.subscription_tier || 'free';

  // Fetch usage data on mount
  useEffect(() => {
    if (user) {
      subscriptionsApi.getUsage()
        .then(setUsage)
        .catch(console.error);
    }
  }, [user]);

  const handleManagePlan = async () => {
    setIsLoading(true);
    try {
      const response = await subscriptionsApi.createPortal(window.location.href);
      window.location.href = response.portal_url;
    } catch (error) {
      console.error('Error opening billing portal:', error);
      setIsLoading(false);
    }
  };

  // Progress bar component
  const ProgressBar = ({ label, used, limit, percent }: { label: string; used: number; limit: number; percent: number }) => {
    const isNearLimit = percent >= 80;
    const isAtLimit = percent >= 100;

    return (
      <div className="mb-2">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-300">{label}</span>
          <span className={isAtLimit ? "text-red-400" : isNearLimit ? "text-yellow-400" : "text-gray-300"}>
            {used} / {limit}
          </span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-1.5">
          <div
            className={`h-1.5 rounded-full transition-all ${
              isAtLimit ? "bg-red-500" : isNearLimit ? "bg-yellow-500" : "bg-emerald-500"
            }`}
            style={{ width: `${Math.min(percent, 100)}%` }}
          />
        </div>
      </div>
    );
  };

  // Show "Manage Plan" card for paid users with usage stats
  if (tier !== 'free') {
    const planName = tier === 'pro' ? 'Pro' : 'Starter';

    return (
      <div className="mx-auto mb-10 w-full max-w-60 rounded-2xl bg-gradient-to-br from-emerald-600 to-teal-700 px-4 py-5">
        <div className="text-center mb-3">
          <div className="mb-2 text-2xl">
            <svg className="w-8 h-8 mx-auto text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="font-semibold text-white">
            {planName} Plan
          </h3>
        </div>

        {/* Usage Stats */}
        {usage && (
          <div className="mb-4">
            <ProgressBar
              label="Alerts"
              used={usage.alerts_sent}
              limit={usage.alerts_limit}
              percent={usage.alerts_usage_percent}
            />
            {usage.exports_limit > 0 && (
              <ProgressBar
                label="Exports"
                used={usage.exports_count}
                limit={usage.exports_limit}
                percent={(usage.exports_count / usage.exports_limit) * 100}
              />
            )}
          </div>
        )}

        <button
          onClick={handleManagePlan}
          disabled={isLoading}
          className="flex items-center justify-center w-full p-3 font-medium text-emerald-600 rounded-lg bg-white text-theme-sm hover:bg-emerald-50 transition-colors disabled:opacity-50"
        >
          {isLoading ? 'Loading...' : 'Manage Plan'}
        </button>
      </div>
    );
  }

  // Show "Upgrade to Pro" card for free users with usage stats
  return (
    <div className="mx-auto mb-10 w-full max-w-60 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 px-4 py-5">
      <div className="text-center mb-3">
        <div className="mb-2 text-2xl">
          <svg className="w-8 h-8 mx-auto text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <h3 className="font-semibold text-white">
          Free Plan
        </h3>
      </div>

      {/* Usage Stats for Free Users */}
      {usage && (
        <div className="mb-4">
          <ProgressBar
            label="Alerts"
            used={usage.alerts_sent}
            limit={usage.alerts_limit}
            percent={usage.alerts_usage_percent}
          />
        </div>
      )}

      <p className="mb-4 text-blue-100 text-theme-sm text-center">
        Upgrade for more alerts & CSV exports.
      </p>
      <Link
        to="/pricing"
        className="flex items-center justify-center p-3 font-medium text-blue-600 rounded-lg bg-white text-theme-sm hover:bg-blue-50 transition-colors"
      >
        View Plans
      </Link>
    </div>
  );
}
