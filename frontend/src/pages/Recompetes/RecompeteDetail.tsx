import { useEffect, useState } from "react";
import { useParams, Link } from "react-router";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";

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

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex flex-col sm:flex-row sm:justify-between py-3 border-b border-gray-100 dark:border-gray-700">
      <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">{label}</dt>
      <dd className="mt-1 sm:mt-0 text-sm text-gray-900 dark:text-white">{value || "N/A"}</dd>
    </div>
  );
}

export default function RecompeteDetail() {
  const { id } = useParams<{ id: string }>();
  const [recompete, setRecompete] = useState<RecompeteData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchRecompete = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `${import.meta.env.VITE_API_URL || "https://bidking-api.fly.dev/api/v1"}/public/recompetes/${id}`
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
              <div className="mt-3">
                <DaysBadge days={recompete.days_until_expiration} />
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
