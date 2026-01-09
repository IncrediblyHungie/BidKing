import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useAlertsStore } from "../../stores/alertsStore";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";
import Button from "../../components/ui/button/Button";
import toast from "react-hot-toast";

// Format date helper
function formatDate(dateString: string | null): string {
  if (!dateString) return "Never";
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// Frequency badge
function FrequencyBadge({ frequency }: { frequency: string }) {
  const colors: Record<string, string> = {
    realtime: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    daily: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    weekly: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  };

  return (
    <span className={`px-2 py-1 text-xs font-medium rounded ${colors[frequency] || "bg-gray-100 text-gray-800"}`}>
      {frequency.charAt(0).toUpperCase() + frequency.slice(1)}
    </span>
  );
}

export default function AlertProfilesList() {
  const {
    alertProfiles,
    isLoading,
    error,
    fetchAlertProfiles,
    deleteAlertProfile,
    toggleProfileActive,
  } = useAlertsStore();

  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    fetchAlertProfiles();
  }, []);

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to delete "${name}"?`)) return;

    setDeletingId(id);
    try {
      await deleteAlertProfile(id);
      toast.success("Alert profile deleted");
    } catch {
      toast.error("Failed to delete alert profile");
    }
    setDeletingId(null);
  };

  const handleToggle = async (id: string) => {
    try {
      await toggleProfileActive(id);
      toast.success("Alert profile updated");
    } catch {
      toast.error("Failed to update alert profile");
    }
  };

  return (
    <>
      <PageMeta title="Alert Profiles | BidKing" description="Manage your contract alert profiles" />
      <PageBreadcrumb pageTitle="Alert Profiles" />

      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Your Alert Profiles</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Get notified when new opportunities match your criteria
            </p>
          </div>
          <Link to="/alerts/create">
            <Button size="sm">Create New Profile</Button>
          </Link>
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
        ) : alertProfiles.length === 0 ? (
          /* Empty state */
          <div className="p-12 text-center bg-white rounded-lg shadow dark:bg-gray-800">
            <div className="mb-4">
              <svg className="w-16 h-16 mx-auto text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            </div>
            <h3 className="mb-2 text-lg font-medium text-gray-900 dark:text-white">No alert profiles yet</h3>
            <p className="mb-6 text-gray-500 dark:text-gray-400">
              Create your first alert profile to get notified about matching opportunities
            </p>
            <Link to="/alerts/create">
              <Button>Create Your First Profile</Button>
            </Link>
          </div>
        ) : (
          /* Alert profiles list */
          <div className="grid gap-4">
            {alertProfiles.map((profile) => (
              <div
                key={profile.id}
                className="p-5 bg-white rounded-lg shadow dark:bg-gray-800"
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  {/* Profile info */}
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                        {profile.name}
                      </h3>
                      <FrequencyBadge frequency={profile.alert_frequency} />
                      <span
                        className={`px-2 py-1 text-xs rounded ${
                          profile.is_active
                            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                            : "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400"
                        }`}
                      >
                        {profile.is_active ? "Active" : "Paused"}
                      </span>
                    </div>

                    {/* Criteria summary */}
                    <div className="flex flex-wrap gap-2 mt-3">
                      {profile.naics_codes.length > 0 && (
                        <span className="px-2 py-1 text-xs bg-gray-100 rounded dark:bg-gray-700">
                          NAICS: {profile.naics_codes.slice(0, 3).join(", ")}
                          {profile.naics_codes.length > 3 && ` +${profile.naics_codes.length - 3}`}
                        </span>
                      )}
                      {profile.keywords.length > 0 && (
                        <span className="px-2 py-1 text-xs bg-gray-100 rounded dark:bg-gray-700">
                          Keywords: {profile.keywords.slice(0, 3).join(", ")}
                          {profile.keywords.length > 3 && ` +${profile.keywords.length - 3}`}
                        </span>
                      )}
                      {profile.states.length > 0 && (
                        <span className="px-2 py-1 text-xs bg-gray-100 rounded dark:bg-gray-700">
                          States: {profile.states.slice(0, 3).join(", ")}
                          {profile.states.length > 3 && ` +${profile.states.length - 3}`}
                        </span>
                      )}
                      {profile.set_aside_types.length > 0 && (
                        <span className="px-2 py-1 text-xs bg-gray-100 rounded dark:bg-gray-700">
                          Set-Aside: {profile.set_aside_types.length} types
                        </span>
                      )}
                      <span className="px-2 py-1 text-xs bg-gray-100 rounded dark:bg-gray-700">
                        Min Score: {profile.min_likelihood_score}
                      </span>
                    </div>

                    {/* Stats */}
                    <div className="flex gap-6 mt-3 text-sm text-gray-500 dark:text-gray-400">
                      <span>Matches: {profile.match_count}</span>
                      <span>Last alert: {formatDate(profile.last_alert_sent)}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleToggle(profile.id)}
                      className={`px-3 py-2 text-sm rounded-lg border ${
                        profile.is_active
                          ? "border-yellow-300 text-yellow-700 hover:bg-yellow-50 dark:border-yellow-600 dark:text-yellow-400 dark:hover:bg-yellow-900/20"
                          : "border-green-300 text-green-700 hover:bg-green-50 dark:border-green-600 dark:text-green-400 dark:hover:bg-green-900/20"
                      }`}
                    >
                      {profile.is_active ? "Pause" : "Activate"}
                    </button>
                    <Link
                      to={`/alerts/${profile.id}/edit`}
                      className="px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700"
                    >
                      Edit
                    </Link>
                    <button
                      onClick={() => handleDelete(profile.id, profile.name)}
                      disabled={deletingId === profile.id}
                      className="px-3 py-2 text-sm text-red-600 border border-red-300 rounded-lg hover:bg-red-50 disabled:opacity-50 dark:border-red-600 dark:text-red-400 dark:hover:bg-red-900/20"
                    >
                      {deletingId === profile.id ? "Deleting..." : "Delete"}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
