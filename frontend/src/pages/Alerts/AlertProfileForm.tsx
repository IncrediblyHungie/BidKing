import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router";
import { useAlertsStore } from "../../stores/alertsStore";
import PageBreadcrumb from "../../components/common/PageBreadcrumb";
import PageMeta from "../../components/common/PageMeta";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import Button from "../../components/ui/button/Button";
import toast from "react-hot-toast";
import { AlertProfileCreate } from "../../types";

// Common NAICS codes for IT/Software
const COMMON_NAICS = [
  { code: "541511", description: "Custom Computer Programming Services" },
  { code: "541512", description: "Computer Systems Design Services" },
  { code: "541519", description: "Other Computer Related Services" },
  { code: "518210", description: "Data Processing, Hosting, and Related Services" },
  { code: "541690", description: "Other Scientific and Technical Consulting Services" },
];

// Set-aside types
const SET_ASIDE_TYPES = [
  { value: "SBA", label: "Small Business Set-Aside" },
  { value: "8A", label: "8(a) Business Development" },
  { value: "WOSB", label: "Women-Owned Small Business" },
  { value: "EDWOSB", label: "Economically Disadvantaged WOSB" },
  { value: "SDVOSB", label: "Service-Disabled Veteran-Owned SB" },
  { value: "HUBZONE", label: "HUBZone" },
];

// US States
const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
];

export default function AlertProfileForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(id);

  const { selectedProfile, isLoading, fetchAlertProfile, createAlertProfile, updateAlertProfile } = useAlertsStore();

  const [formData, setFormData] = useState<AlertProfileCreate>({
    name: "",
    naics_codes: [],
    psc_codes: [],
    keywords: [],
    excluded_keywords: [],
    agencies: [],
    states: [],
    set_aside_types: [],
    min_likelihood_score: 40,
    alert_frequency: "daily",
    is_active: true,
  });

  const [keywordsInput, setKeywordsInput] = useState("");
  const [excludedKeywordsInput, setExcludedKeywordsInput] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isEditing && id) {
      fetchAlertProfile(id);
    }
  }, [id, isEditing]);

  useEffect(() => {
    if (isEditing && selectedProfile) {
      setFormData({
        name: selectedProfile.name,
        naics_codes: selectedProfile.naics_codes,
        psc_codes: selectedProfile.psc_codes,
        keywords: selectedProfile.keywords,
        excluded_keywords: selectedProfile.excluded_keywords,
        agencies: selectedProfile.agencies,
        states: selectedProfile.states,
        set_aside_types: selectedProfile.set_aside_types,
        min_likelihood_score: selectedProfile.min_likelihood_score,
        alert_frequency: selectedProfile.alert_frequency,
        is_active: selectedProfile.is_active,
      });
      setKeywordsInput(selectedProfile.keywords.join(", "));
      setExcludedKeywordsInput(selectedProfile.excluded_keywords.join(", "));
    }
  }, [selectedProfile, isEditing]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      toast.error("Please enter a profile name");
      return;
    }

    // Parse keywords from comma-separated inputs
    const keywords = keywordsInput.split(",").map(k => k.trim()).filter(k => k);
    const excludedKeywords = excludedKeywordsInput.split(",").map(k => k.trim()).filter(k => k);

    const data = {
      ...formData,
      keywords,
      excluded_keywords: excludedKeywords,
    };

    setIsSaving(true);
    try {
      if (isEditing && id) {
        await updateAlertProfile(id, data);
        toast.success("Alert profile updated");
      } else {
        await createAlertProfile(data);
        toast.success("Alert profile created");
      }
      navigate("/alerts");
    } catch {
      toast.error(isEditing ? "Failed to update profile" : "Failed to create profile");
    }
    setIsSaving(false);
  };

  const toggleNaicsCode = (code: string) => {
    setFormData((prev) => ({
      ...prev,
      naics_codes: prev.naics_codes?.includes(code)
        ? prev.naics_codes.filter((c) => c !== code)
        : [...(prev.naics_codes || []), code],
    }));
  };

  const toggleSetAside = (value: string) => {
    setFormData((prev) => ({
      ...prev,
      set_aside_types: prev.set_aside_types?.includes(value)
        ? prev.set_aside_types.filter((t) => t !== value)
        : [...(prev.set_aside_types || []), value],
    }));
  };

  const toggleState = (state: string) => {
    setFormData((prev) => ({
      ...prev,
      states: prev.states?.includes(state)
        ? prev.states.filter((s) => s !== state)
        : [...(prev.states || []), state],
    }));
  };

  if (isLoading && isEditing) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="w-8 h-8 border-4 border-blue-500 rounded-full animate-spin border-t-transparent"></div>
      </div>
    );
  }

  return (
    <>
      <PageMeta
        title={`${isEditing ? "Edit" : "Create"} Alert Profile | BidKing`}
        description="Configure your alert profile settings"
      />
      <PageBreadcrumb pageTitle={isEditing ? "Edit Alert Profile" : "Create Alert Profile"} />

      <div className="max-w-3xl">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Profile Name */}
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Profile Details</h3>
            <div className="space-y-4">
              <div>
                <Label>Profile Name <span className="text-error-500">*</span></Label>
                <Input
                  type="text"
                  placeholder="e.g., IT Services - California"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                />
              </div>
              <div>
                <Label>Alert Frequency</Label>
                <select
                  className="w-full px-4 py-2.5 text-sm border rounded-lg dark:bg-gray-900 dark:border-gray-700"
                  value={formData.alert_frequency}
                  onChange={(e) => setFormData({ ...formData, alert_frequency: e.target.value as any })}
                >
                  <option value="realtime">Real-time (Pro tier)</option>
                  <option value="daily">Daily Digest</option>
                  <option value="weekly">Weekly Digest</option>
                </select>
              </div>
            </div>
          </div>

          {/* NAICS Codes */}
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">NAICS Codes</h3>
            <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
              Select the industry codes you want to track
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {COMMON_NAICS.map((naics) => (
                <label
                  key={naics.code}
                  className={`flex items-center gap-3 p-3 border rounded-lg cursor-pointer ${
                    formData.naics_codes?.includes(naics.code)
                      ? "border-brand-500 bg-brand-50 dark:bg-brand-900/20"
                      : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={formData.naics_codes?.includes(naics.code)}
                    onChange={() => toggleNaicsCode(naics.code)}
                    className="w-4 h-4"
                  />
                  <div>
                    <div className="font-mono text-sm font-medium">{naics.code}</div>
                    <div className="text-xs text-gray-500">{naics.description}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Keywords */}
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Keywords</h3>
            <div className="space-y-4">
              <div>
                <Label>Include Keywords</Label>
                <Input
                  type="text"
                  placeholder="python, data analytics, AWS (comma-separated)"
                  value={keywordsInput}
                  onChange={(e) => setKeywordsInput(e.target.value)}
                />
                <p className="mt-1 text-xs text-gray-500">
                  Opportunities must contain at least one of these keywords
                </p>
              </div>
              <div>
                <Label>Exclude Keywords</Label>
                <Input
                  type="text"
                  placeholder="clearance required, classified (comma-separated)"
                  value={excludedKeywordsInput}
                  onChange={(e) => setExcludedKeywordsInput(e.target.value)}
                />
                <p className="mt-1 text-xs text-gray-500">
                  Opportunities with these keywords will be filtered out
                </p>
              </div>
            </div>
          </div>

          {/* Set-Aside Types */}
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Set-Aside Types</h3>
            <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
              Only show opportunities with these set-asides (leave empty for all)
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {SET_ASIDE_TYPES.map((type) => (
                <label
                  key={type.value}
                  className={`flex items-center gap-3 p-3 border rounded-lg cursor-pointer ${
                    formData.set_aside_types?.includes(type.value)
                      ? "border-brand-500 bg-brand-50 dark:bg-brand-900/20"
                      : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={formData.set_aside_types?.includes(type.value)}
                    onChange={() => toggleSetAside(type.value)}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">{type.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* States */}
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Geographic Focus</h3>
            <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
              Only show opportunities in these states (leave empty for all)
            </p>
            <div className="flex flex-wrap gap-2">
              {US_STATES.map((state) => (
                <button
                  key={state}
                  type="button"
                  onClick={() => toggleState(state)}
                  className={`px-3 py-1 text-sm rounded-lg border ${
                    formData.states?.includes(state)
                      ? "border-brand-500 bg-brand-500 text-white"
                      : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  }`}
                >
                  {state}
                </button>
              ))}
            </div>
          </div>

          {/* Score Filter */}
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Opportunity Score</h3>
            <div>
              <Label>Minimum Likelihood Score</Label>
              <select
                className="w-full px-4 py-2.5 text-sm border rounded-lg dark:bg-gray-900 dark:border-gray-700"
                value={formData.min_likelihood_score}
                onChange={(e) => setFormData({ ...formData, min_likelihood_score: Number(e.target.value) })}
              >
                <option value={0}>Any score (0+)</option>
                <option value={40}>Medium or higher (40+)</option>
                <option value={70}>High only (70+)</option>
              </select>
              <p className="mt-1 text-xs text-gray-500">
                Higher scores indicate greater likelihood the contract is under $100K
              </p>
            </div>
          </div>

          {/* Active Toggle */}
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="w-5 h-5"
              />
              <div>
                <span className="font-medium text-gray-900 dark:text-white">Active</span>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Receive alerts when new opportunities match this profile
                </p>
              </div>
            </label>
          </div>

          {/* Form Actions */}
          <div className="flex gap-4">
            <Button type="submit" disabled={isSaving}>
              {isSaving ? "Saving..." : isEditing ? "Update Profile" : "Create Profile"}
            </Button>
            <Link
              to="/alerts"
              className="inline-flex items-center px-4 py-2 text-sm font-medium border rounded-lg hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700"
            >
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </>
  );
}
