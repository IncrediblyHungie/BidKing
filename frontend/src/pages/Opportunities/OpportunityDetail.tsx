import { useEffect, useState } from "react";
import { useParams, Link } from "react-router";
import { useOpportunitiesStore } from "../../stores/opportunitiesStore";
import { useAuthStore } from "../../stores/authStore";
import { opportunitiesApi, OpportunityScore } from "../../api/opportunities";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";
import Button from "../../components/ui/button/Button";
import toast from "react-hot-toast";

// AI Summary type definition
interface AISummary {
  summary?: string;
  period_of_performance?: string;
  contract_type?: string;
  clearance_required?: string;
  labor_categories?: Array<{ title: string; quantity?: number; level?: string }>;
  technologies?: string[];
  certifications_required?: string[];
  set_aside_info?: string;
  location?: string;
  incumbent?: string;
  estimated_value?: { low?: number; high?: number; basis?: string };
  key_dates?: { proposal_due?: string; questions_due?: string; anticipated_start?: string };
  evaluation_factors?: string[];
  naics_code?: string;
  contract_number?: string;
  source_documents?: string[];
  status?: string;
}

// Score badge component
function ScoreBadge({ score }: { score: number }) {
  const getScoreColor = () => {
    if (score >= 70) return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
    if (score >= 40) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
    return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
  };

  const getScoreLabel = () => {
    if (score >= 70) return "High likelihood under $100K";
    if (score >= 40) return "Medium likelihood under $100K";
    return "Low likelihood under $100K";
  };

  return (
    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg ${getScoreColor()}`}>
      <span className="text-2xl font-bold">{score}</span>
      <span className="text-sm">{getScoreLabel()}</span>
    </div>
  );
}

// Personalized Score Card component
function PersonalizedScoreCard({ score }: { score: OpportunityScore }) {
  const getScoreColor = (s: number) => {
    if (s >= 70) return "text-green-600 dark:text-green-400";
    if (s >= 40) return "text-yellow-600 dark:text-yellow-400";
    return "text-red-600 dark:text-red-400";
  };

  return (
    <div className="p-4 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
      <div className="flex items-center gap-3 mb-3">
        <div className="flex items-center justify-center w-12 h-12 bg-purple-100 dark:bg-purple-900/40 rounded-full">
          <span className={`text-2xl font-bold ${getScoreColor(score.overall_score)}`}>
            {score.overall_score}
          </span>
        </div>
        <div>
          <div className="font-semibold text-purple-900 dark:text-purple-100">Your Fit Score</div>
          <div className="text-sm text-purple-700 dark:text-purple-300">Based on your company profile</div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="flex justify-between">
          <span className="text-purple-700 dark:text-purple-300">NAICS Match</span>
          <span className={`font-medium ${getScoreColor(score.capability_score)}`}>{score.capability_score}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-purple-700 dark:text-purple-300">Eligibility</span>
          <span className={`font-medium ${getScoreColor(score.eligibility_score)}`}>{score.eligibility_score}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-purple-700 dark:text-purple-300">Scale Fit</span>
          <span className={`font-medium ${getScoreColor(score.scale_score)}`}>{score.scale_score}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-purple-700 dark:text-purple-300">Clearance</span>
          <span className={`font-medium ${getScoreColor(score.clearance_score)}`}>{score.clearance_score}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-purple-700 dark:text-purple-300">Contract Type</span>
          <span className={`font-medium ${getScoreColor(score.contract_type_score)}`}>{score.contract_type_score}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-purple-700 dark:text-purple-300">Timeline</span>
          <span className={`font-medium ${getScoreColor(score.timeline_score)}`}>{score.timeline_score}%</span>
        </div>
      </div>
    </div>
  );
}

// Format date helper
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "N/A";
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

// Format datetime helper
function formatDateTime(dateString: string | null | undefined): string {
  if (!dateString) return "N/A";
  return new Date(dateString).toLocaleString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

// Format currency helper
function formatCurrency(amount: number | string | null | undefined): string {
  if (amount == null) return "N/A";
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(num);
}

// Days until deadline with color
function DeadlineDisplay({ dateString }: { dateString: string | null | undefined }) {
  if (!dateString) return <span className="text-gray-500">No deadline set</span>;

  const now = new Date();
  const deadline = new Date(dateString);
  const diffTime = deadline.getTime() - now.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  let colorClass = "text-gray-900 dark:text-white";
  let urgencyText = "";

  if (diffDays < 0) {
    colorClass = "text-red-600 dark:text-red-400";
    urgencyText = "Expired";
  } else if (diffDays === 0) {
    colorClass = "text-red-600 dark:text-red-400";
    urgencyText = "Due today!";
  } else if (diffDays <= 3) {
    colorClass = "text-orange-600 dark:text-orange-400";
    urgencyText = `${diffDays} days left`;
  } else if (diffDays <= 7) {
    colorClass = "text-yellow-600 dark:text-yellow-400";
    urgencyText = `${diffDays} days left`;
  } else {
    urgencyText = `${diffDays} days left`;
  }

  return (
    <div>
      <div className={`text-lg font-semibold ${colorClass}`}>{formatDateTime(dateString)}</div>
      <div className={`text-sm ${colorClass}`}>{urgencyText}</div>
    </div>
  );
}

// Section Header component
function SectionHeader({ title, icon }: { title: string; icon?: string }) {
  return (
    <h3 className="flex items-center gap-2 mb-4 text-lg font-semibold text-gray-900 dark:text-white border-b pb-2 dark:border-gray-700">
      {icon && <span>{icon}</span>}
      {title}
    </h3>
  );
}

// Info Row component
function InfoRow({ label, value, className = "" }: { label: string; value: React.ReactNode; className?: string }) {
  return (
    <div className={`flex flex-col sm:flex-row sm:justify-between py-2 border-b border-gray-100 dark:border-gray-700 last:border-0 ${className}`}>
      <span className="text-sm font-medium text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-sm text-gray-900 dark:text-white sm:text-right sm:max-w-[60%]">{value || "N/A"}</span>
    </div>
  );
}

export default function OpportunityDetail() {
  const { id } = useParams<{ id: string }>();
  const { selectedOpportunity, isLoading, error, fetchOpportunity, saveOpportunity } = useOpportunitiesStore();
  const { isAuthenticated } = useAuthStore();
  const [isSaving, setIsSaving] = useState(false);
  const [personalizedScore, setPersonalizedScore] = useState<OpportunityScore | null>(null);
  const [aiSummary, setAiSummary] = useState<AISummary | null>(null);
  const [aiSummaryLoading, setAiSummaryLoading] = useState(false);

  useEffect(() => {
    if (id) {
      fetchOpportunity(id);
    }
  }, [id]);

  // Fetch AI summary
  useEffect(() => {
    const fetchAiSummary = async () => {
      if (!id) return;
      setAiSummaryLoading(true);
      try {
        const apiUrl = import.meta.env.VITE_API_URL || 'https://api.bidking.ai/api/v1';
        const response = await fetch(`${apiUrl}/opportunities/${id}/ai-summary`);
        if (response.ok) {
          const data = await response.json();
          // API returns { has_summary: true, summary: {...} }
          if (data && data.has_summary && data.summary) {
            setAiSummary(data.summary);
          }
        }
      } catch (err) {
        console.debug("Could not fetch AI summary:", err);
      } finally {
        setAiSummaryLoading(false);
      }
    };

    fetchAiSummary();
  }, [id]);

  // Fetch personalized score for authenticated users
  useEffect(() => {
    const fetchPersonalizedScore = async () => {
      if (!id || !isAuthenticated) return;

      try {
        const scoreResponse = await opportunitiesApi.getScore(id);
        if ('has_score' in scoreResponse && scoreResponse.has_score === false) {
          // No score available
          setPersonalizedScore(null);
        } else {
          setPersonalizedScore(scoreResponse as OpportunityScore);
        }
      } catch (err) {
        // Silently fail - personalized scores are optional
        console.debug("Could not fetch personalized score:", err);
      }
    };

    fetchPersonalizedScore();
  }, [id, isAuthenticated]);

  const handleSave = async () => {
    if (!id) return;
    setIsSaving(true);
    try {
      await saveOpportunity(id);
      toast.success("Opportunity saved to your pipeline");
    } catch {
      toast.error("Failed to save opportunity");
    }
    setIsSaving(false);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="w-8 h-8 border-4 border-blue-500 rounded-full animate-spin border-t-transparent"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-600 bg-red-50 rounded-lg dark:bg-red-900/20 dark:text-red-400">
        {error}
      </div>
    );
  }

  if (!selectedOpportunity) {
    return (
      <div className="p-4 text-gray-600 bg-gray-50 rounded-lg dark:bg-gray-800 dark:text-gray-400">
        Opportunity not found
      </div>
    );
  }

  const opp = selectedOpportunity;

  // Build contracting office address string
  const officeAddress = opp.contracting_office_address;
  const addressParts = [];
  if (officeAddress) {
    if (officeAddress.street) addressParts.push(officeAddress.street);
    if (officeAddress.city) addressParts.push(officeAddress.city);
    if (officeAddress.state) addressParts.push(officeAddress.state);
    if (officeAddress.zip) addressParts.push(officeAddress.zip);
    if (officeAddress.country) addressParts.push(officeAddress.country);
  }

  return (
    <>
      <PageMeta title={`${opp.title} | BidKing`} description={opp.description || ""} />
      <PageBreadcrumb pageTitle="Opportunity Details" />

      <div className="space-y-6">
        {/* Header */}
        <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{opp.title}</h1>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                {opp.solicitation_number && (
                  <span className="mr-3">Solicitation: <span className="font-mono">{opp.solicitation_number}</span></span>
                )}
                <span>Notice ID: <span className="font-mono">{opp.notice_id}</span></span>
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                {opp.notice_type && (
                  <span className="px-2 py-1 text-xs bg-gray-100 rounded dark:bg-gray-700">
                    {opp.notice_type}
                  </span>
                )}
                {opp.set_aside_type && (
                  <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded dark:bg-blue-900/30 dark:text-blue-400">
                    {opp.set_aside_description || opp.set_aside_type}
                  </span>
                )}
                {opp.status && opp.status !== "active" && (
                  <span className="px-2 py-1 text-xs bg-orange-100 text-orange-800 rounded dark:bg-orange-900/30 dark:text-orange-400">
                    {opp.status}
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-col gap-3">
              {/* Show personalized score card if available */}
              {personalizedScore && (
                <PersonalizedScoreCard score={personalizedScore} />
              )}
              {/* Generic score badge */}
              <div>
                <div className="text-xs text-gray-500 mb-1">
                  {personalizedScore ? "Generic Score" : "Likelihood Score"}
                </div>
                <ScoreBadge score={opp.likelihood_score} />
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={handleSave} disabled={isSaving}>
                  {isSaving ? "Saving..." : "Save to Pipeline"}
                </Button>
                {opp.ui_link && (
                  <a
                    href={opp.ui_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center px-4 py-2 text-sm font-medium border rounded-lg hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700"
                  >
                    View on SAM.gov →
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Related Notice Alert */}
        {opp.related_notice_id && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg dark:bg-blue-900/20 dark:border-blue-800">
            <div className="flex items-center gap-2">
              <span className="text-blue-600 dark:text-blue-400">ℹ️</span>
              <span className="text-sm text-blue-800 dark:text-blue-300">
                Related Notice: <span className="font-mono">{opp.related_notice_id}</span>
              </span>
            </div>
          </div>
        )}

        {/* Key Details Grid */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Deadline Card */}
          <div className="p-5 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="text-sm font-medium text-gray-500 uppercase dark:text-gray-400">Response Deadline</h3>
            <div className="mt-2">
              <DeadlineDisplay dateString={opp.response_deadline} />
            </div>
          </div>

          {/* Agency Card */}
          <div className="p-5 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="text-sm font-medium text-gray-500 uppercase dark:text-gray-400">Agency</h3>
            <div className="mt-2">
              <div className="text-lg font-semibold text-gray-900 dark:text-white">{opp.department_name || opp.agency_name || "N/A"}</div>
              {opp.sub_tier && <div className="text-sm text-gray-600 dark:text-gray-400">{opp.sub_tier}</div>}
              {opp.office_name && <div className="text-sm text-gray-500">{opp.office_name}</div>}
            </div>
          </div>

          {/* Classification Card */}
          <div className="p-5 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="text-sm font-medium text-gray-500 uppercase dark:text-gray-400">Classification</h3>
            <div className="mt-2 space-y-2">
              <div>
                <span className="text-xs text-gray-500">NAICS:</span>
                <span className="ml-2 font-mono text-gray-900 dark:text-white">{opp.naics_code || "N/A"}</span>
                {opp.naics_description && (
                  <div className="text-sm text-gray-500">{opp.naics_description}</div>
                )}
              </div>
              {opp.psc_code && (
                <div>
                  <span className="text-xs text-gray-500">PSC:</span>
                  <span className="ml-2 font-mono text-gray-900 dark:text-white">{opp.psc_code}</span>
                  {opp.psc_description && (
                    <div className="text-sm text-gray-500">{opp.psc_description}</div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Description */}
        <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
          <SectionHeader title="Description" icon="📋" />
          <div className="prose prose-sm max-w-none dark:prose-invert">
            {opp.description ? (
              opp.description.startsWith("http") ? (
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <p className="text-gray-600 dark:text-gray-400 mb-3">
                    Full description available on SAM.gov
                  </p>
                  <a
                    href={opp.ui_link || `https://sam.gov/opp/${opp.notice_id}/view`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                    View Full Description on SAM.gov
                  </a>
                </div>
              ) : (
                <p className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">{opp.description}</p>
              )
            ) : (
              <p className="text-gray-500 italic">No description available</p>
            )}
          </div>
        </div>

        {/* AI Summary Section */}
        {(aiSummary || aiSummaryLoading) && (
          <div className="p-6 bg-gradient-to-r from-purple-50 to-indigo-50 dark:from-purple-900/20 dark:to-indigo-900/20 rounded-lg shadow border border-purple-100 dark:border-purple-800">
            <SectionHeader title="AI Analysis" icon="🤖" />

            {aiSummaryLoading ? (
              <div className="flex items-center gap-3 text-gray-500">
                <div className="w-5 h-5 border-2 border-purple-500 rounded-full animate-spin border-t-transparent"></div>
                <span>Analyzing PDF attachments...</span>
              </div>
            ) : aiSummary ? (
              <div className="space-y-6">
                {/* Summary */}
                {aiSummary.summary && (
                  <div>
                    <h4 className="text-sm font-semibold text-purple-800 dark:text-purple-300 mb-2">What They Want</h4>
                    <p className="text-gray-700 dark:text-gray-300">{aiSummary.summary}</p>
                  </div>
                )}

                {/* Key Details Grid */}
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {/* Estimated Value */}
                  {aiSummary.estimated_value && (aiSummary.estimated_value.low || aiSummary.estimated_value.high) && (
                    <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-purple-200 dark:border-purple-700">
                      <div className="text-xs font-medium text-purple-600 dark:text-purple-400 mb-1">💰 Estimated Value</div>
                      <div className="text-lg font-bold text-gray-900 dark:text-white">
                        {aiSummary.estimated_value.low && aiSummary.estimated_value.high
                          ? `${formatCurrency(aiSummary.estimated_value.low)} - ${formatCurrency(aiSummary.estimated_value.high)}`
                          : formatCurrency(aiSummary.estimated_value.low || aiSummary.estimated_value.high)
                        }
                      </div>
                      {aiSummary.estimated_value.basis && (
                        <div className="text-xs text-gray-500 mt-1">{aiSummary.estimated_value.basis}</div>
                      )}
                    </div>
                  )}

                  {/* Period of Performance */}
                  {aiSummary.period_of_performance && (
                    <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-purple-200 dark:border-purple-700">
                      <div className="text-xs font-medium text-purple-600 dark:text-purple-400 mb-1">📅 Period of Performance</div>
                      <div className="text-gray-900 dark:text-white font-medium">{aiSummary.period_of_performance}</div>
                    </div>
                  )}

                  {/* Contract Type */}
                  {aiSummary.contract_type && (
                    <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-purple-200 dark:border-purple-700">
                      <div className="text-xs font-medium text-purple-600 dark:text-purple-400 mb-1">📝 Contract Type</div>
                      <div className="text-gray-900 dark:text-white font-medium">{aiSummary.contract_type}</div>
                    </div>
                  )}

                  {/* Clearance Required */}
                  {aiSummary.clearance_required && (
                    <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-purple-200 dark:border-purple-700">
                      <div className="text-xs font-medium text-purple-600 dark:text-purple-400 mb-1">🔒 Clearance Required</div>
                      <div className="text-gray-900 dark:text-white font-medium">{aiSummary.clearance_required}</div>
                    </div>
                  )}

                  {/* Location */}
                  {aiSummary.location && (
                    <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-purple-200 dark:border-purple-700">
                      <div className="text-xs font-medium text-purple-600 dark:text-purple-400 mb-1">📍 Work Location</div>
                      <div className="text-gray-900 dark:text-white font-medium">{aiSummary.location}</div>
                    </div>
                  )}

                  {/* Incumbent */}
                  {aiSummary.incumbent && (
                    <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-purple-200 dark:border-purple-700">
                      <div className="text-xs font-medium text-purple-600 dark:text-purple-400 mb-1">🏢 Current Incumbent</div>
                      <div className="text-gray-900 dark:text-white font-medium">{aiSummary.incumbent}</div>
                    </div>
                  )}
                </div>

                {/* Technologies */}
                {aiSummary.technologies && aiSummary.technologies.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-purple-800 dark:text-purple-300 mb-2">💻 Technologies Required</h4>
                    <div className="flex flex-wrap gap-2">
                      {aiSummary.technologies.map((tech, i) => (
                        <span key={i} className="px-3 py-1 bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 rounded-full text-sm">
                          {tech}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Labor Categories */}
                {aiSummary.labor_categories && aiSummary.labor_categories.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-purple-800 dark:text-purple-300 mb-2">👥 Labor Categories</h4>
                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                      {aiSummary.labor_categories.map((lc, i) => (
                        <div key={i} className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                          <div className="font-medium text-gray-900 dark:text-white">{lc.title}</div>
                          <div className="text-sm text-gray-500">
                            {lc.level && <span className="mr-2">{lc.level}</span>}
                            {lc.quantity && <span>×{lc.quantity}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Certifications */}
                {aiSummary.certifications_required && aiSummary.certifications_required.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-purple-800 dark:text-purple-300 mb-2">📜 Certifications Required</h4>
                    <div className="flex flex-wrap gap-2">
                      {aiSummary.certifications_required.map((cert, i) => (
                        <span key={i} className="px-3 py-1 bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300 rounded-full text-sm">
                          {cert}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Evaluation Factors */}
                {aiSummary.evaluation_factors && aiSummary.evaluation_factors.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-purple-800 dark:text-purple-300 mb-2">⚖️ Evaluation Factors</h4>
                    <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1">
                      {aiSummary.evaluation_factors.map((factor, i) => (
                        <li key={i}>{factor}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Source Documents */}
                {aiSummary.source_documents && aiSummary.source_documents.length > 0 && (
                  <div className="text-xs text-gray-500 pt-4 border-t border-purple-200 dark:border-purple-700">
                    <span className="font-medium">Analyzed from:</span> {aiSummary.source_documents.join(", ")}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}

        {/* Award Information (if awarded) */}
        {(opp.award_number || opp.awardee_name || opp.award_amount) && (
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <SectionHeader title="Award Details" icon="🏆" />
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <InfoRow label="Award Number" value={opp.award_number} />
                {opp.task_delivery_order_number && (
                  <InfoRow label="Task/Delivery Order" value={opp.task_delivery_order_number} />
                )}
                {opp.modification_number && (
                  <InfoRow label="Modification Number" value={opp.modification_number} />
                )}
                <InfoRow label="Award Date" value={formatDate(opp.award_date)} />
              </div>
              <div>
                <InfoRow label="Award Amount" value={formatCurrency(opp.award_amount)} />
                <InfoRow label="Awardee Name" value={opp.awardee_name} />
                {opp.awardee_uei && (
                  <InfoRow label="Awardee UEI" value={<span className="font-mono">{opp.awardee_uei}</span>} />
                )}
              </div>
            </div>
          </div>
        )}

        {/* Location & Dates */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Place of Performance */}
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <SectionHeader title="Place of Performance" icon="📍" />
            {opp.pop_city || opp.pop_state || opp.pop_country ? (
              <div className="space-y-1">
                {opp.pop_city && <div className="text-gray-700 dark:text-gray-300">{opp.pop_city}</div>}
                {(opp.pop_state || opp.pop_zip) && (
                  <div className="text-gray-700 dark:text-gray-300">
                    {opp.pop_state}{opp.pop_zip ? ` ${opp.pop_zip}` : ""}
                  </div>
                )}
                {opp.pop_country && <div className="text-gray-500">{opp.pop_country}</div>}
              </div>
            ) : (
              <p className="text-gray-500 italic">Location not specified</p>
            )}
          </div>

          {/* Key Dates */}
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <SectionHeader title="Key Dates" icon="📅" />
            <div className="space-y-1">
              <InfoRow label="Posted Date" value={formatDate(opp.posted_date)} />
              {opp.original_published_date && (
                <InfoRow label="Original Published" value={formatDateTime(opp.original_published_date)} />
              )}
              <InfoRow label="Response Deadline" value={formatDateTime(opp.response_deadline)} />
              <InfoRow label="Archive Date" value={formatDate(opp.archive_date)} />
              {opp.original_inactive_date && (
                <InfoRow label="Inactive Date" value={formatDate(opp.original_inactive_date)} />
              )}
              {opp.inactive_policy && (
                <InfoRow label="Inactive Policy" value={opp.inactive_policy} />
              )}
            </div>
          </div>
        </div>

        {/* Contract Details */}
        {(opp.contract_type || opp.authority || opp.initiative || addressParts.length > 0) && (
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <SectionHeader title="Contract Details" icon="📑" />
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                {opp.contract_type && <InfoRow label="Contract Type" value={opp.contract_type} />}
                {opp.authority && <InfoRow label="Authority" value={opp.authority} />}
                {opp.initiative && <InfoRow label="Initiative" value={opp.initiative} />}
              </div>
              {addressParts.length > 0 && (
                <div>
                  <InfoRow
                    label="Contracting Office Address"
                    value={
                      <div className="text-right">
                        {officeAddress?.street && <div>{officeAddress.street}</div>}
                        <div>
                          {officeAddress?.city && `${officeAddress.city}, `}
                          {officeAddress?.state} {officeAddress?.zip}
                        </div>
                        {officeAddress?.country && <div>{officeAddress.country}</div>}
                      </div>
                    }
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Attachments/Links */}
        {opp.attachments && opp.attachments.length > 0 && (
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <SectionHeader title="Attachments & Links" icon="📎" />
            <div className="space-y-3">
              {opp.attachments.map((att, index) => (
                <div key={att.id || index} className="flex items-center justify-between p-3 border rounded-lg dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 dark:text-white truncate">
                      {att.name || "Attachment"}
                    </div>
                    {att.description && (
                      <div className="text-sm text-gray-500 truncate">{att.description}</div>
                    )}
                    <div className="flex gap-3 text-xs text-gray-400 mt-1">
                      {att.resource_type && <span>{att.resource_type}</span>}
                      {att.file_type && <span>{att.file_type}</span>}
                      {att.file_size && <span>{(att.file_size / 1024).toFixed(1)} KB</span>}
                      {att.posted_date && <span>{formatDate(att.posted_date)}</span>}
                    </div>
                  </div>
                  {att.id && (
                    <a
                      href={`${import.meta.env.VITE_API_URL || 'https://api.bidking.ai/api/v1'}/opportunities/attachments/${att.id}/download`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-4 px-3 py-1 text-sm text-brand-600 hover:text-brand-700 dark:text-brand-400"
                    >
                      Open →
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Points of Contact */}
        {opp.points_of_contact && opp.points_of_contact.length > 0 && (
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <SectionHeader title="Points of Contact" icon="👤" />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {opp.points_of_contact.map((poc, index) => (
                <div key={index} className="p-4 border rounded-lg dark:border-gray-700">
                  {poc.type && (
                    <div className="text-xs text-gray-500 uppercase mb-1">{poc.type}</div>
                  )}
                  <div className="font-medium text-gray-900 dark:text-white">{poc.name || "Contact"}</div>
                  {poc.title && <div className="text-sm text-gray-500">{poc.title}</div>}
                  <div className="mt-2 space-y-1">
                    {poc.email && (
                      <a href={`mailto:${poc.email}`} className="block text-sm text-brand-500 hover:underline">
                        ✉️ {poc.email}
                      </a>
                    )}
                    {poc.phone && (
                      <a href={`tel:${poc.phone}`} className="block text-sm text-brand-500 hover:underline">
                        📞 {poc.phone}
                      </a>
                    )}
                    {poc.fax && (
                      <div className="text-sm text-gray-500">
                        📠 {poc.fax}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* History */}
        {opp.history && opp.history.length > 0 && (
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <SectionHeader title="History" icon="📜" />
            <div className="space-y-3">
              {opp.history.map((entry, index) => (
                <div key={entry.id || index} className="flex gap-4 p-3 border-l-4 border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/30 rounded-r-lg">
                  <div className="flex-1">
                    <div className="font-medium text-gray-900 dark:text-white">{entry.action}</div>
                    {entry.description && (
                      <div className="text-sm text-gray-500 mt-1">{entry.description}</div>
                    )}
                  </div>
                  <div className="text-sm text-gray-500 whitespace-nowrap">
                    {formatDateTime(entry.changed_at)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Back button */}
        <div className="flex justify-between items-center">
          <Link to="/opportunities" className="text-brand-500 hover:text-brand-600">
            ← Back to Opportunities
          </Link>
          {opp.ui_link && (
            <a
              href={opp.ui_link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand-500 hover:text-brand-600"
            >
              View on SAM.gov →
            </a>
          )}
        </div>
      </div>
    </>
  );
}
