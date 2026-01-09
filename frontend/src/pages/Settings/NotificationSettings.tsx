import { useState, useEffect } from "react";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";
import { apiClient } from "../../api/client";

interface NotificationSettings {
  email_reminders_enabled: boolean;
  email_deadline_warnings: boolean;
  deadline_warning_days: number;
}

export default function NotificationSettings() {
  const [settings, setSettings] = useState<NotificationSettings>({
    email_reminders_enabled: true,
    email_deadline_warnings: true,
    deadline_warning_days: 5,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await apiClient.get("/users/me/notification-settings");
      setSettings(response.data);
    } catch (error) {
      console.error("Failed to fetch notification settings:", error);
      setMessage({ type: "error", text: "Failed to load settings" });
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await apiClient.patch("/users/me/notification-settings", settings);
      setMessage({ type: "success", text: "Settings saved successfully!" });
      setTimeout(() => setMessage(null), 3000);
    } catch (error) {
      console.error("Failed to save notification settings:", error);
      setMessage({ type: "error", text: "Failed to save settings" });
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = (field: keyof NotificationSettings) => {
    setSettings((prev) => ({
      ...prev,
      [field]: !prev[field],
    }));
  };

  const handleDaysChange = (value: number) => {
    setSettings((prev) => ({
      ...prev,
      deadline_warning_days: Math.max(1, Math.min(30, value)),
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500"></div>
      </div>
    );
  }

  return (
    <>
      <PageMeta
        title="Notification Settings | BidKing"
        description="Manage your email notification preferences"
      />
      <PageBreadcrumb pageTitle="Notification Settings" />

      <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] lg:p-6">
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            Email Notifications
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Configure how and when BidKing sends you email notifications.
          </p>
        </div>

        {message && (
          <div
            className={`mb-6 p-4 rounded-lg ${
              message.type === "success"
                ? "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400"
                : "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400"
            }`}
          >
            {message.text}
          </div>
        )}

        <div className="space-y-6">
          {/* Custom Reminders Toggle */}
          <div className="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-white/[0.02]">
            <div>
              <h4 className="font-medium text-gray-800 dark:text-white/90">
                Custom Reminders
              </h4>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Receive emails for opportunities with custom reminder dates you set in your pipeline.
              </p>
            </div>
            <button
              type="button"
              onClick={() => handleToggle("email_reminders_enabled")}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 ${
                settings.email_reminders_enabled
                  ? "bg-brand-500"
                  : "bg-gray-200 dark:bg-gray-700"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  settings.email_reminders_enabled ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Deadline Warnings Toggle */}
          <div className="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-white/[0.02]">
            <div>
              <h4 className="font-medium text-gray-800 dark:text-white/90">
                Deadline Warnings
              </h4>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Get notified when opportunities in your pipeline are approaching their response deadline.
              </p>
            </div>
            <button
              type="button"
              onClick={() => handleToggle("email_deadline_warnings")}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 ${
                settings.email_deadline_warnings
                  ? "bg-brand-500"
                  : "bg-gray-200 dark:bg-gray-700"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  settings.email_deadline_warnings ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Days Before Deadline */}
          {settings.email_deadline_warnings && (
            <div className="p-4 rounded-lg bg-gray-50 dark:bg-white/[0.02]">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium text-gray-800 dark:text-white/90">
                    Warning Days Before Deadline
                  </h4>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    How many days before a deadline should we send you a warning email?
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => handleDaysChange(settings.deadline_warning_days - 1)}
                    className="w-8 h-8 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors flex items-center justify-center"
                  >
                    -
                  </button>
                  <span className="w-12 text-center font-semibold text-gray-800 dark:text-white">
                    {settings.deadline_warning_days}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDaysChange(settings.deadline_warning_days + 1)}
                    className="w-8 h-8 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors flex items-center justify-center"
                  >
                    +
                  </button>
                </div>
              </div>
              <div className="mt-4">
                <input
                  type="range"
                  min="1"
                  max="30"
                  value={settings.deadline_warning_days}
                  onChange={(e) => handleDaysChange(parseInt(e.target.value))}
                  className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-brand-500"
                />
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                  <span>1 day</span>
                  <span>30 days</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Save Button */}
        <div className="mt-8 flex justify-end">
          <button
            type="button"
            onClick={saveSettings}
            disabled={saving}
            className="px-6 py-2.5 bg-brand-500 text-white font-medium rounded-lg hover:bg-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </div>
    </>
  );
}
