import { useEffect, useState } from "react";
import { useParams, Link } from "react-router";
import { useOpportunitiesStore } from "../../stores/opportunitiesStore";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";
import Button from "../../components/ui/button/Button";
import toast from "react-hot-toast";

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

// Format date helper
function formatDate(dateString: string | null): string {
  if (!dateString) return "N/A";
  return new Date(dateString).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

// Days until deadline with color
function DeadlineDisplay({ dateString }: { dateString: string | null }) {
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
      <div className={`text-lg font-semibold ${colorClass}`}>{formatDate(dateString)}</div>
      <div className={`text-sm ${colorClass}`}>{urgencyText}</div>
    </div>
  );
}

export default function OpportunityDetail() {
  const { id } = useParams<{ id: string }>();
  const { selectedOpportunity, isLoading, error, fetchOpportunity, saveOpportunity } = useOpportunitiesStore();
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (id) {
      fetchOpportunity(id);
    }
  }, [id]);

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
                {opp.solicitation_number || opp.notice_id}
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                {opp.type && (
                  <span className="px-2 py-1 text-xs bg-gray-100 rounded dark:bg-gray-700">
                    {opp.type_description || opp.type}
                  </span>
                )}
                {opp.set_aside_type && (
                  <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded dark:bg-blue-900/30 dark:text-blue-400">
                    {opp.set_aside_description || opp.set_aside_type}
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-col gap-3">
              <ScoreBadge score={opp.likelihood_score} />
              <div className="flex gap-2">
                <Button size="sm" onClick={handleSave} disabled={isSaving}>
                  {isSaving ? "Saving..." : "Save to Pipeline"}
                </Button>
                {opp.sam_gov_link && (
                  <a
                    href={opp.sam_gov_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center px-4 py-2 text-sm font-medium border rounded-lg hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700"
                  >
                    View on SAM.gov
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>

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
              <div className="text-lg font-semibold text-gray-900 dark:text-white">{opp.agency_name || "N/A"}</div>
              {opp.sub_agency_name && <div className="text-sm text-gray-500">{opp.sub_agency_name}</div>}
              {opp.office_name && <div className="text-sm text-gray-500">{opp.office_name}</div>}
            </div>
          </div>

          {/* NAICS/PSC Card */}
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
          <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Description</h3>
          <div className="prose prose-sm max-w-none dark:prose-invert">
            {opp.description ? (
              <p className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">{opp.description}</p>
            ) : (
              <p className="text-gray-500 italic">No description available</p>
            )}
          </div>
        </div>

        {/* Location & Dates */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Place of Performance */}
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Place of Performance</h3>
            {opp.pop_city || opp.pop_state || opp.pop_country ? (
              <div className="space-y-1">
                {opp.pop_city && <div className="text-gray-700 dark:text-gray-300">{opp.pop_city}</div>}
                {opp.pop_state && <div className="text-gray-700 dark:text-gray-300">{opp.pop_state} {opp.pop_zip}</div>}
                {opp.pop_country && <div className="text-gray-500">{opp.pop_country}</div>}
              </div>
            ) : (
              <p className="text-gray-500 italic">Location not specified</p>
            )}
          </div>

          {/* Key Dates */}
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Key Dates</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-500">Posted Date:</span>
                <span className="text-gray-900 dark:text-white">{formatDate(opp.posted_date)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Response Deadline:</span>
                <span className="text-gray-900 dark:text-white">{formatDate(opp.response_deadline)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Archive Date:</span>
                <span className="text-gray-900 dark:text-white">{formatDate(opp.archive_date)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Points of Contact */}
        {opp.points_of_contact && opp.points_of_contact.length > 0 && (
          <div className="p-6 bg-white rounded-lg shadow dark:bg-gray-800">
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Points of Contact</h3>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {opp.points_of_contact.map((poc, index) => (
                <div key={index} className="p-4 border rounded-lg dark:border-gray-700">
                  <div className="font-medium text-gray-900 dark:text-white">{poc.name || "Contact"}</div>
                  {poc.title && <div className="text-sm text-gray-500">{poc.title}</div>}
                  {poc.email && (
                    <a href={`mailto:${poc.email}`} className="block mt-2 text-sm text-brand-500 hover:underline">
                      {poc.email}
                    </a>
                  )}
                  {poc.phone && (
                    <a href={`tel:${poc.phone}`} className="block text-sm text-brand-500 hover:underline">
                      {poc.phone}
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Back button */}
        <div>
          <Link to="/opportunities" className="text-brand-500 hover:text-brand-600">
            &larr; Back to Opportunities
          </Link>
        </div>
      </div>
    </>
  );
}
