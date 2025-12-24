import { useState, useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router";
import { useCompanyStore } from "../../stores/companyStore";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import Select from "../../components/form/Select";
import Button from "../../components/ui/button/Button";
import toast from "react-hot-toast";

// Common NAICS codes for federal contracting
const COMMON_NAICS = [
  { code: "541511", description: "Custom Computer Programming Services" },
  { code: "541512", description: "Computer Systems Design Services" },
  { code: "541519", description: "Other Computer Related Services" },
  { code: "518210", description: "Data Processing, Hosting, and Related Services" },
  { code: "541330", description: "Engineering Services" },
  { code: "541611", description: "Administrative Management Consulting" },
  { code: "541612", description: "Human Resources Consulting" },
  { code: "541613", description: "Marketing Consulting Services" },
  { code: "541614", description: "Process/Logistics/Physical Distribution Consulting" },
  { code: "541618", description: "Other Management Consulting Services" },
  { code: "541690", description: "Other Scientific and Technical Consulting" },
  { code: "541990", description: "All Other Professional, Scientific, and Technical Services" },
  { code: "561110", description: "Office Administrative Services" },
  { code: "561210", description: "Facilities Support Services" },
  { code: "561320", description: "Temporary Help Services" },
  { code: "561499", description: "All Other Business Support Services" },
];

// Common certifications
const COMMON_CERTS = [
  { type: "8(a)", description: "SBA 8(a) Business Development Program" },
  { type: "HUBZone", description: "Historically Underutilized Business Zone" },
  { type: "SDVOSB", description: "Service-Disabled Veteran-Owned Small Business" },
  { type: "VOSB", description: "Veteran-Owned Small Business" },
  { type: "WOSB", description: "Women-Owned Small Business" },
  { type: "EDWOSB", description: "Economically Disadvantaged WOSB" },
  { type: "SDB", description: "Small Disadvantaged Business" },
];

// US States
const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
];

export default function CompanyOnboardingPage() {
  const navigate = useNavigate();
  const location = useLocation();

  // Detect if this is edit mode (inside dashboard layout) vs initial onboarding
  const isEditMode = location.pathname === "/settings/company";

  const {
    profile,
    naicsCodes,
    certifications,
    capabilityStatements,
    isLoading,
    isUploading,
    error,
    fetchProfile,
    fetchNAICSCodes,
    fetchCertifications,
    fetchCapabilityStatements,
    createProfile,
    updateProfile,
    addNAICS,
    removeNAICS,
    addCert,
    removeCert,
    uploadCapabilityStatement,
    removeCapabilityStatement,
    completeOnboarding,
    skipOnboarding,
    clearError,
  } = useCompanyStore();

  // File input ref for capability statement
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 4;

  // Load existing data in edit mode
  useEffect(() => {
    if (isEditMode) {
      fetchProfile();
      fetchNAICSCodes();
      fetchCertifications();
      fetchCapabilityStatements();
    }
  }, [isEditMode, fetchProfile, fetchNAICSCodes, fetchCertifications, fetchCapabilityStatements]);

  // Form data for step 1
  const [basicInfo, setBasicInfo] = useState({
    company_name: "",
    uei: "",
    cage_code: "",
    business_size: "small",
    employee_count: "",
    annual_revenue: "",
    headquarters_state: "",
  });

  // Form data for step 2 (NAICS)
  const [selectedNAICS, setSelectedNAICS] = useState("");
  const [customNAICS, setCustomNAICS] = useState("");

  // Form data for step 3 (Certifications)
  const [selectedCert, setSelectedCert] = useState("");

  // Form data for step 4 (Preferences)
  const [preferences, setPreferences] = useState({
    min_contract_value: "",
    max_contract_value: "",
    typical_contract_size: "small",
    facility_clearance: "None",
    has_sci_capability: false,
    pref_firm_fixed_price: 3,
    pref_time_materials: 3,
    pref_cost_plus: 3,
    pref_idiq: 3,
    geographic_preference: "national",
    min_days_to_respond: "14",
    can_rush_proposals: false,
  });

  // Load existing profile data
  useEffect(() => {
    if (profile) {
      setBasicInfo({
        company_name: profile.company_name || "",
        uei: profile.uei || "",
        cage_code: profile.cage_code || "",
        business_size: profile.business_size || "small",
        employee_count: profile.employee_count?.toString() || "",
        annual_revenue: profile.annual_revenue?.toString() || "",
        headquarters_state: profile.headquarters_state || "",
      });
      setPreferences({
        min_contract_value: profile.min_contract_value?.toString() || "",
        max_contract_value: profile.max_contract_value?.toString() || "",
        typical_contract_size: profile.typical_contract_size || "small",
        facility_clearance: profile.facility_clearance || "None",
        has_sci_capability: profile.has_sci_capability || false,
        pref_firm_fixed_price: profile.pref_firm_fixed_price || 3,
        pref_time_materials: profile.pref_time_materials || 3,
        pref_cost_plus: profile.pref_cost_plus || 3,
        pref_idiq: profile.pref_idiq || 3,
        geographic_preference: profile.geographic_preference || "national",
        min_days_to_respond: profile.min_days_to_respond?.toString() || "14",
        can_rush_proposals: profile.can_rush_proposals || false,
      });
      // Start from where they left off
      if (profile.onboarding_step > 0 && profile.onboarding_step < 5) {
        setCurrentStep(Math.min(profile.onboarding_step + 1, totalSteps));
      }
    }
  }, [profile]);

  // Clear errors when changing steps
  useEffect(() => {
    clearError();
  }, [currentStep, clearError]);

  // Handle basic info input changes
  const handleBasicInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setBasicInfo((prev) => ({ ...prev, [name]: value }));
  };

  // Handle basic info select changes
  const handleBasicSelectChange = (name: string) => (value: string) => {
    setBasicInfo((prev) => ({ ...prev, [name]: value }));
  };

  // Handle preference input changes
  const handlePrefInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setPreferences((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  // Handle preference select changes
  const handlePrefSelectChange = (name: string) => (value: string) => {
    setPreferences((prev) => ({ ...prev, [name]: value }));
  };

  // Handle slider change for contract type preferences
  const handleSliderChange = (name: string, value: number) => {
    setPreferences((prev) => ({ ...prev, [name]: value }));
  };

  // Step 1: Save basic company info
  const handleSaveBasicInfo = async () => {
    if (!basicInfo.company_name.trim()) {
      toast.error("Company name is required");
      return;
    }

    try {
      const data = {
        company_name: basicInfo.company_name,
        uei: basicInfo.uei || null,
        cage_code: basicInfo.cage_code || null,
        business_size: basicInfo.business_size,
        employee_count: basicInfo.employee_count ? parseInt(basicInfo.employee_count) : null,
        annual_revenue: basicInfo.annual_revenue ? parseFloat(basicInfo.annual_revenue) : null,
        headquarters_state: basicInfo.headquarters_state || null,
      };

      if (profile) {
        await updateProfile(data);
      } else {
        await createProfile(data);
      }
      toast.success("Company info saved!");
      setCurrentStep(2);
    } catch (err: any) {
      toast.error(err.message || "Failed to save company info");
    }
  };

  // Step 2: Add NAICS code
  const handleAddNAICS = async () => {
    const code = selectedNAICS || customNAICS;
    if (!code) {
      toast.error("Please select or enter a NAICS code");
      return;
    }

    // Check if already added
    if (naicsCodes.some((n) => n.naics_code === code)) {
      toast.error("NAICS code already added");
      return;
    }

    try {
      const naicsData = COMMON_NAICS.find((n) => n.code === code);
      await addNAICS({
        naics_code: code,
        naics_description: naicsData?.description,
        is_primary: naicsCodes.length === 0, // First one is primary
      });
      setSelectedNAICS("");
      setCustomNAICS("");
      toast.success("NAICS code added!");
    } catch (err: any) {
      toast.error(err.message || "Failed to add NAICS code");
    }
  };

  // Step 3: Add certification
  const handleAddCert = async () => {
    if (!selectedCert) {
      toast.error("Please select a certification");
      return;
    }

    // Check if already added
    if (certifications.some((c) => c.certification_type === selectedCert)) {
      toast.error("Certification already added");
      return;
    }

    try {
      await addCert({
        certification_type: selectedCert,
        is_active: true,
      });
      setSelectedCert("");
      toast.success("Certification added!");
    } catch (err: any) {
      toast.error(err.message || "Failed to add certification");
    }
  };

  // Step 4: Save preferences and complete
  const handleSavePreferences = async () => {
    try {
      // Update the profile with preferences
      const updatedProfile = await updateProfile({
        min_contract_value: preferences.min_contract_value ? parseFloat(preferences.min_contract_value) : null,
        max_contract_value: preferences.max_contract_value ? parseFloat(preferences.max_contract_value) : null,
        typical_contract_size: preferences.typical_contract_size,
        facility_clearance: preferences.facility_clearance,
        has_sci_capability: preferences.has_sci_capability,
        pref_firm_fixed_price: preferences.pref_firm_fixed_price,
        pref_time_materials: preferences.pref_time_materials,
        pref_cost_plus: preferences.pref_cost_plus,
        pref_idiq: preferences.pref_idiq,
        geographic_preference: preferences.geographic_preference,
        min_days_to_respond: parseInt(preferences.min_days_to_respond),
        can_rush_proposals: preferences.can_rush_proposals,
      });

      if (isEditMode) {
        // In edit mode, check the RETURNED profile (not stale closure value)
        if (!updatedProfile?.onboarding_completed) {
          await completeOnboarding();
        }
        // Show success toast and navigate to opportunities
        toast.success("Company settings saved! Your scores have been updated.");
        navigate("/opportunities");
      } else {
        // In initial onboarding, always complete
        await completeOnboarding();
        toast.success("Onboarding complete! Your scores will now be personalized.");
        navigate("/opportunities");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to save settings");
    }
  };

  // Skip onboarding
  const handleSkip = async () => {
    try {
      await skipOnboarding();
      toast.success("Skipped onboarding. You can complete your profile later.");
      navigate("/dashboard");
    } catch (err: any) {
      toast.error(err.message || "Failed to skip onboarding");
    }
  };

  // Handle capability statement file upload
  const handleCapabilityUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const validTypes = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
    if (!validTypes.includes(file.type)) {
      toast.error("Please upload a PDF or DOCX file");
      return;
    }

    // Validate file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      toast.error("File size must be less than 10MB");
      return;
    }

    try {
      await uploadCapabilityStatement(file, undefined, capabilityStatements.length === 0);
      toast.success("Capability statement uploaded and analyzed! Scores will be recalculated.");
      // Reset the file input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to upload capability statement");
    }
  };

  // Handle capability statement deletion
  const handleRemoveCapability = async (capId: string) => {
    try {
      await removeCapabilityStatement(capId);
      toast.success("Capability statement removed");
    } catch (err: any) {
      toast.error(err.message || "Failed to remove capability statement");
    }
  };

  // Progress indicator - clickable in edit mode
  const renderProgress = () => {
    const stepLabels = ["Company", "NAICS", "Certs", "Preferences"];

    const handleStepClick = (step: number) => {
      // In edit mode, allow navigating to any step
      // In onboarding mode, only allow going back to completed steps
      if (isEditMode) {
        setCurrentStep(step);
      } else if (step < currentStep) {
        setCurrentStep(step);
      }
    };

    return (
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          {[1, 2, 3, 4].map((step) => {
            const isClickable = isEditMode || step < currentStep;
            return (
              <button
                key={step}
                onClick={() => handleStepClick(step)}
                disabled={!isClickable}
                className={`flex items-center justify-center w-10 h-10 rounded-full border-2 font-semibold transition-all ${
                  step < currentStep
                    ? "bg-green-500 border-green-500 text-white"
                    : step === currentStep
                    ? "bg-blue-500 border-blue-500 text-white"
                    : "bg-gray-100 border-gray-300 text-gray-400 dark:bg-gray-700 dark:border-gray-600"
                } ${isClickable ? "cursor-pointer hover:scale-110 hover:shadow-md" : "cursor-default"}`}
              >
                {step < currentStep ? "✓" : step}
              </button>
            );
          })}
        </div>
        <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
          {stepLabels.map((label, index) => (
            <button
              key={label}
              onClick={() => handleStepClick(index + 1)}
              disabled={!isEditMode && index + 1 >= currentStep}
              className={`${
                isEditMode || index + 1 < currentStep
                  ? "cursor-pointer hover:text-blue-500"
                  : "cursor-default"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    );
  };

  // Step 1: Basic Company Info
  const renderStep1 = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-800 dark:text-white">Company Information</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Basic information about your company for opportunity matching.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="sm:col-span-2">
          <Label>Company Name <span className="text-red-500">*</span></Label>
          <Input
            name="company_name"
            placeholder="Your company legal name"
            value={basicInfo.company_name}
            onChange={handleBasicInputChange}
          />
        </div>

        <div>
          <Label>UEI (Unique Entity Identifier)</Label>
          <Input
            name="uei"
            placeholder="12-character UEI"
            max="12"
            value={basicInfo.uei}
            onChange={handleBasicInputChange}
          />
        </div>

        <div>
          <Label>CAGE Code</Label>
          <Input
            name="cage_code"
            placeholder="5-character CAGE"
            max="5"
            value={basicInfo.cage_code}
            onChange={handleBasicInputChange}
          />
        </div>

        <div>
          <Label>Business Size</Label>
          <Select
            defaultValue={basicInfo.business_size}
            onChange={handleBasicSelectChange("business_size")}
            options={[
              { value: "small", label: "Small Business" },
              { value: "large", label: "Large Business" },
              { value: "other", label: "Other" },
            ]}
          />
        </div>

        <div>
          <Label>Employee Count</Label>
          <Input
            name="employee_count"
            type="number"
            placeholder="Number of employees"
            value={basicInfo.employee_count}
            onChange={handleBasicInputChange}
          />
        </div>

        <div>
          <Label>Annual Revenue ($)</Label>
          <Input
            name="annual_revenue"
            type="number"
            placeholder="Annual revenue in dollars"
            value={basicInfo.annual_revenue}
            onChange={handleBasicInputChange}
          />
        </div>

        <div>
          <Label>Headquarters State</Label>
          <Select
            placeholder="Select state..."
            defaultValue={basicInfo.headquarters_state}
            onChange={handleBasicSelectChange("headquarters_state")}
            options={US_STATES.map((s) => ({ value: s, label: s }))}
          />
        </div>
      </div>

      <div className="flex justify-between pt-4">
        {!isEditMode ? (
          <Button variant="outline" onClick={handleSkip} disabled={isLoading}>
            Skip for now
          </Button>
        ) : (
          <div /> // Spacer for layout
        )}
        <Button onClick={handleSaveBasicInfo} disabled={isLoading}>
          {isLoading ? "Saving..." : "Next: NAICS Codes"}
        </Button>
      </div>
    </div>
  );

  // Step 2: NAICS Codes
  const renderStep2 = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-800 dark:text-white">NAICS Codes</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Add the NAICS codes that match your company's capabilities. At least one is required.
      </p>

      {/* Current NAICS codes */}
      {naicsCodes.length > 0 && (
        <div className="space-y-2 mb-4">
          <Label>Your NAICS Codes:</Label>
          <div className="flex flex-wrap gap-2">
            {naicsCodes.map((naics) => (
              <div
                key={naics.id}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
                  naics.is_primary
                    ? "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
                    : "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
                }`}
              >
                <span className="font-medium">{naics.naics_code}</span>
                {naics.naics_description && (
                  <span className="text-xs opacity-75 hidden sm:inline">
                    - {naics.naics_description.slice(0, 30)}...
                  </span>
                )}
                {naics.is_primary && <span className="text-xs font-semibold">(Primary)</span>}
                <button
                  onClick={() => removeNAICS(naics.id)}
                  className="ml-1 text-red-500 hover:text-red-700"
                  disabled={isLoading}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Add NAICS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <Label>Select Common NAICS</Label>
          <Select
            placeholder="Choose from common codes..."
            defaultValue={selectedNAICS}
            onChange={(value) => setSelectedNAICS(value)}
            options={COMMON_NAICS.map((n) => ({
              value: n.code,
              label: `${n.code} - ${n.description}`,
            }))}
          />
        </div>
        <div>
          <Label>Or Enter Custom NAICS</Label>
          <Input
            name="custom_naics"
            placeholder="Enter 6-digit NAICS"
            max="6"
            value={customNAICS}
            onChange={(e) => setCustomNAICS(e.target.value)}
          />
        </div>
      </div>

      <Button variant="outline" onClick={handleAddNAICS} disabled={isLoading}>
        + Add NAICS Code
      </Button>

      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={() => setCurrentStep(1)} disabled={isLoading}>
          Back
        </Button>
        <Button
          onClick={() => {
            if (naicsCodes.length === 0) {
              toast.error("Please add at least one NAICS code");
              return;
            }
            setCurrentStep(3);
          }}
          disabled={isLoading}
        >
          Next: Certifications
        </Button>
      </div>
    </div>
  );

  // Step 3: Certifications
  const renderStep3 = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-800 dark:text-white">Certifications & Set-Asides</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Add any small business certifications you hold. These affect eligibility scoring.
      </p>

      {/* Current certifications */}
      {certifications.length > 0 && (
        <div className="space-y-2 mb-4">
          <Label>Your Certifications:</Label>
          <div className="flex flex-wrap gap-2">
            {certifications.map((cert) => (
              <div
                key={cert.id}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
              >
                <span className="font-medium">{cert.certification_type}</span>
                <button
                  onClick={() => removeCert(cert.id)}
                  className="ml-1 text-red-500 hover:text-red-700"
                  disabled={isLoading}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Add certification */}
      <div>
        <Label>Add Certification</Label>
        <div className="flex gap-2">
          <Select
            placeholder="Select certification..."
            defaultValue={selectedCert}
            onChange={(value) => setSelectedCert(value)}
            className="flex-1"
            options={COMMON_CERTS.map((c) => ({
              value: c.type,
              label: `${c.type} - ${c.description}`,
            }))}
          />
          <Button variant="outline" onClick={handleAddCert} disabled={isLoading}>
            Add
          </Button>
        </div>
      </div>

      <p className="text-xs text-gray-400 dark:text-gray-500">
        No certifications? That's okay! You can still pursue full and open competitions.
      </p>

      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={() => setCurrentStep(2)} disabled={isLoading}>
          Back
        </Button>
        <Button onClick={() => setCurrentStep(4)} disabled={isLoading}>
          Next: Preferences
        </Button>
      </div>
    </div>
  );

  // Step 4: Preferences
  const renderStep4 = () => (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-800 dark:text-white">Contract Preferences</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Tell us your preferences to personalize opportunity scoring.
      </p>

      {/* Contract Size */}
      <div className="space-y-4">
        <h3 className="font-medium text-gray-700 dark:text-gray-300">Contract Size Preferences</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <Label>Typical Contract Size</Label>
            <Select
              defaultValue={preferences.typical_contract_size}
              onChange={handlePrefSelectChange("typical_contract_size")}
              options={[
                { value: "micro", label: "Micro (<$25K)" },
                { value: "small", label: "Small ($25K-$250K)" },
                { value: "medium", label: "Medium ($250K-$1M)" },
                { value: "large", label: "Large ($1M-$10M)" },
                { value: "enterprise", label: "Enterprise (>$10M)" },
              ]}
            />
          </div>
          <div>
            <Label>Min Contract Value ($)</Label>
            <Input
              name="min_contract_value"
              type="number"
              placeholder="Minimum"
              value={preferences.min_contract_value}
              onChange={handlePrefInputChange}
            />
          </div>
          <div>
            <Label>Max Contract Value ($)</Label>
            <Input
              name="max_contract_value"
              type="number"
              placeholder="Maximum"
              value={preferences.max_contract_value}
              onChange={handlePrefInputChange}
            />
          </div>
        </div>
      </div>

      {/* Security Clearance */}
      <div className="space-y-4">
        <h3 className="font-medium text-gray-700 dark:text-gray-300">Security Clearance</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label>Facility Clearance Level</Label>
            <Select
              defaultValue={preferences.facility_clearance}
              onChange={handlePrefSelectChange("facility_clearance")}
              options={[
                { value: "None", label: "None" },
                { value: "Confidential", label: "Confidential" },
                { value: "Secret", label: "Secret" },
                { value: "Top Secret", label: "Top Secret" },
              ]}
            />
          </div>
          <div className="flex items-center pt-6">
            <input
              type="checkbox"
              name="has_sci_capability"
              checked={preferences.has_sci_capability}
              onChange={handlePrefInputChange}
              className="w-4 h-4 rounded border-gray-300 text-blue-600"
            />
            <label className="ml-2 text-sm text-gray-700 dark:text-gray-300">
              SCI Capability (Sensitive Compartmented Information)
            </label>
          </div>
        </div>
      </div>

      {/* Contract Type Preferences */}
      <div className="space-y-4">
        <h3 className="font-medium text-gray-700 dark:text-gray-300">Contract Type Preferences (1-5)</h3>
        <p className="text-xs text-gray-400">Rate your preference: 1 = Avoid, 3 = Neutral, 5 = Prefer</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { key: "pref_firm_fixed_price", label: "Firm Fixed Price" },
            { key: "pref_time_materials", label: "Time & Materials" },
            { key: "pref_cost_plus", label: "Cost Plus" },
            { key: "pref_idiq", label: "IDIQ/BPA" },
          ].map(({ key, label }) => (
            <div key={key}>
              <Label>{label}</Label>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="1"
                  max="5"
                  value={(preferences as any)[key]}
                  onChange={(e) => handleSliderChange(key, parseInt(e.target.value))}
                  className="flex-1"
                />
                <span className="text-sm font-medium w-4">{(preferences as any)[key]}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Timeline */}
      <div className="space-y-4">
        <h3 className="font-medium text-gray-700 dark:text-gray-300">Response Timeline</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label>Minimum Days to Respond</Label>
            <Input
              name="min_days_to_respond"
              type="number"
              placeholder="Days needed to prepare"
              value={preferences.min_days_to_respond}
              onChange={handlePrefInputChange}
            />
          </div>
          <div className="flex items-center pt-6">
            <input
              type="checkbox"
              name="can_rush_proposals"
              checked={preferences.can_rush_proposals}
              onChange={handlePrefInputChange}
              className="w-4 h-4 rounded border-gray-300 text-blue-600"
            />
            <label className="ml-2 text-sm text-gray-700 dark:text-gray-300">
              Can handle rush proposals (short deadlines)
            </label>
          </div>
        </div>
      </div>

      {/* Capability Statement Upload (Optional) */}
      <div className="space-y-4 border-t border-gray-200 dark:border-gray-700 pt-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium text-gray-700 dark:text-gray-300">Capability Statement</h3>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Optional: Upload your capability statement for better opportunity matching
            </p>
          </div>
          <span className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded">
            Optional
          </span>
        </div>

        {/* Existing capability statements */}
        {capabilityStatements.length > 0 && (
          <div className="space-y-2">
            {capabilityStatements.map((cap) => (
              <div
                key={cap.id}
                className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span className="font-medium text-gray-800 dark:text-gray-200 truncate">
                      {cap.name}
                    </span>
                    {cap.is_default && (
                      <span className="text-xs px-2 py-0.5 bg-blue-100 dark:bg-blue-800 text-blue-700 dark:text-blue-300 rounded">
                        Default
                      </span>
                    )}
                  </div>
                  {cap.keywords && cap.keywords.length > 0 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
                      {cap.keywords.slice(0, 5).join(", ")}
                      {cap.keywords.length > 5 && ` +${cap.keywords.length - 5} more`}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => handleRemoveCapability(cap.id)}
                  className="ml-3 p-1 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                  disabled={isLoading}
                  title="Remove capability statement"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Upload area */}
        <div className="relative">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx"
            onChange={handleCapabilityUpload}
            disabled={isUploading}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
          />
          <div
            className={`flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-lg transition-colors ${
              isUploading
                ? "border-blue-400 bg-blue-50 dark:bg-blue-900/20"
                : "border-gray-300 dark:border-gray-600 hover:border-blue-400 hover:bg-gray-50 dark:hover:bg-gray-700/50"
            }`}
          >
            {isUploading ? (
              <>
                <svg className="w-8 h-8 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span className="mt-2 text-sm text-blue-600 dark:text-blue-400">
                  Analyzing your capability statement...
                </span>
              </>
            ) : (
              <>
                <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <span className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  Drop your capability statement here or click to browse
                </span>
                <span className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                  PDF or DOCX (max 10MB)
                </span>
              </>
            )}
          </div>
        </div>

        <p className="text-xs text-gray-400 dark:text-gray-500">
          We'll use AI to extract your core competencies, differentiators, and keywords
          to improve opportunity matching and personalized scoring.
        </p>
      </div>

      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={() => setCurrentStep(3)} disabled={isLoading || isUploading}>
          Back
        </Button>
        <Button onClick={handleSavePreferences} disabled={isLoading || isUploading}>
          {isLoading ? "Saving..." : isEditMode ? "Save Settings" : "Complete Setup"}
        </Button>
      </div>
    </div>
  );

  // Edit mode: simpler layout that fits inside the dashboard
  if (isEditMode) {
    return (
      <div className="p-4 sm:p-6">
        <div className="max-w-3xl mx-auto">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Company Settings
            </h1>
            <p className="mt-1 text-gray-600 dark:text-gray-400">
              Update your company profile to improve opportunity scoring.
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-6">
            {renderProgress()}

            {error && (
              <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
                {error}
              </div>
            )}

            {currentStep === 1 && renderStep1()}
            {currentStep === 2 && renderStep2()}
            {currentStep === 3 && renderStep3()}
            {currentStep === 4 && renderStep4()}
          </div>
        </div>
      </div>
    );
  }

  // Initial onboarding: full-screen centered layout
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <img
            src="/images/logo/logo.svg"
            alt="BidKing"
            className="h-10 mx-auto mb-6 dark:hidden"
          />
          <img
            src="/images/logo/logo-dark.svg"
            alt="BidKing"
            className="h-10 mx-auto mb-6 hidden dark:block"
          />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Set Up Your Company Profile
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            This information powers personalized opportunity scoring.
          </p>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-6 sm:p-8">
          {renderProgress()}

          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
              {error}
            </div>
          )}

          {currentStep === 1 && renderStep1()}
          {currentStep === 2 && renderStep2()}
          {currentStep === 3 && renderStep3()}
          {currentStep === 4 && renderStep4()}
        </div>

        <p className="text-center text-sm text-gray-500 dark:text-gray-400 mt-6">
          You can update this information anytime in Company Settings.
        </p>
      </div>
    </div>
  );
}
