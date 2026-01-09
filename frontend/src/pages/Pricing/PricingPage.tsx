import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { useAuthStore } from "../../stores/authStore";
import { subscriptionsApi } from "../../api/subscriptions";

interface PlanFeature {
  name: string;
  included: boolean;
}

interface Plan {
  id: string;
  name: string;
  description: string;
  priceMonthly: number;
  priceYearly: number;
  features: PlanFeature[];
  highlighted?: boolean;
  cta: string;
}

const plans: Plan[] = [
  {
    id: "free",
    name: "Free",
    description: "Get started with federal contract tracking",
    priceMonthly: 0,
    priceYearly: 0,
    cta: "Get Started",
    features: [
      { name: "1 alert profile", included: true },
      { name: "10 alerts per month", included: true },
      { name: "3 AI generations per day", included: true },
      { name: "Daily digest emails", included: true },
      { name: "Basic opportunity search", included: true },
      { name: "Instant alerts", included: false },
      { name: "CSV export", included: false },
      { name: "Labor pricing data", included: false },
      { name: "Recompete tracking", included: false },
      { name: "API access", included: false },
    ],
  },
  {
    id: "starter",
    name: "Starter",
    description: "For growing contractors seeking more opportunities",
    priceMonthly: 29,
    priceYearly: 290,
    cta: "Subscribe",
    features: [
      { name: "5 alert profiles", included: true },
      { name: "100 alerts per month", included: true },
      { name: "20 AI generations per day", included: true },
      { name: "Daily & weekly digests", included: true },
      { name: "Full opportunity search", included: true },
      { name: "Instant alerts", included: true },
      { name: "CSV export", included: true },
      { name: "Labor pricing data", included: true },
      { name: "Recompete tracking", included: false },
      { name: "API access", included: false },
    ],
  },
  {
    id: "pro",
    name: "Pro",
    description: "For serious contractors who want every advantage",
    priceMonthly: 79,
    priceYearly: 790,
    cta: "Subscribe",
    highlighted: true,
    features: [
      { name: "20 alert profiles", included: true },
      { name: "500 alerts per month", included: true },
      { name: "100 AI generations per day", included: true },
      { name: "All digest options", included: true },
      { name: "Full opportunity search", included: true },
      { name: "Instant alerts", included: true },
      { name: "CSV export", included: true },
      { name: "Labor pricing data", included: true },
      { name: "Recompete tracking", included: true },
      { name: "API access", included: true },
    ],
  },
];

export default function PricingPage() {
  const [billingPeriod, setBillingPeriod] = useState<"monthly" | "yearly">("monthly");
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);
  const { isAuthenticated, user } = useAuthStore();
  const navigate = useNavigate();

  const currentTier = user?.subscription_tier || "free";

  const handleSubscribe = async (planId: string) => {
    if (planId === "free") {
      if (isAuthenticated) {
        navigate("/dashboard");
      } else {
        navigate("/signup");
      }
      return;
    }

    if (!isAuthenticated) {
      // Redirect to signup with return URL
      navigate(`/signup?plan=${planId}&billing=${billingPeriod}`);
      return;
    }

    // Already subscribed to this plan
    if (currentTier === planId) {
      return;
    }

    setLoadingPlan(planId);
    try {
      const response = await subscriptionsApi.createCheckout({
        tier: planId as "starter" | "pro",
        billing_period: billingPeriod,
        success_url: window.location.origin + "/dashboard?upgraded=true",
        cancel_url: window.location.origin + "/pricing",
      });
      window.location.href = response.checkout_url;
    } catch (error) {
      console.error("Checkout error:", error);
      setLoadingPlan(null);
    }
  };

  const getPrice = (plan: Plan) => {
    return billingPeriod === "monthly" ? plan.priceMonthly : plan.priceYearly;
  };

  const getSavings = (plan: Plan) => {
    if (plan.priceMonthly === 0) return 0;
    return plan.priceMonthly * 12 - plan.priceYearly;
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <span className="text-xl font-bold text-gray-900 dark:text-white">BidKing</span>
          </Link>
          <div className="flex items-center gap-4">
            {isAuthenticated ? (
              <Link
                to="/dashboard"
                className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
              >
                Dashboard
              </Link>
            ) : (
              <>
                <Link
                  to="/signin"
                  className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
                >
                  Sign In
                </Link>
                <Link
                  to="/signup"
                  className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-12 sm:px-6 lg:px-8">
        {/* Title */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
            Simple, Transparent Pricing
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
            Choose the plan that fits your federal contracting needs. All plans include access to SAM.gov opportunities.
          </p>
        </div>

        {/* Billing Toggle */}
        <div className="flex justify-center mb-12">
          <div className="bg-gray-100 dark:bg-gray-800 rounded-xl p-1 flex">
            <button
              onClick={() => setBillingPeriod("monthly")}
              className={`px-6 py-2 rounded-lg text-sm font-medium transition-all ${
                billingPeriod === "monthly"
                  ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm"
                  : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingPeriod("yearly")}
              className={`px-6 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                billingPeriod === "yearly"
                  ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm"
                  : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
              }`}
            >
              Yearly
              <span className="bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 text-xs px-2 py-0.5 rounded-full">
                Save 2 months
              </span>
            </button>
          </div>
        </div>

        {/* Plan Cards */}
        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {plans.map((plan) => {
            const isCurrentPlan = isAuthenticated && currentTier === plan.id;
            const savings = getSavings(plan);

            return (
              <div
                key={plan.id}
                className={`relative bg-white dark:bg-gray-800 rounded-2xl shadow-lg overflow-hidden ${
                  plan.highlighted
                    ? "ring-2 ring-blue-600 dark:ring-blue-500"
                    : "border border-gray-200 dark:border-gray-700"
                }`}
              >
                {/* Popular Badge */}
                {plan.highlighted && (
                  <div className="absolute top-0 right-0 bg-blue-600 text-white text-xs font-semibold px-3 py-1 rounded-bl-lg">
                    Most Popular
                  </div>
                )}

                <div className="p-8">
                  {/* Plan Name */}
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                    {plan.name}
                  </h3>
                  <p className="text-gray-600 dark:text-gray-400 text-sm mb-6">
                    {plan.description}
                  </p>

                  {/* Price */}
                  <div className="mb-6">
                    <div className="flex items-baseline">
                      <span className="text-4xl font-bold text-gray-900 dark:text-white">
                        ${getPrice(plan)}
                      </span>
                      {plan.priceMonthly > 0 && (
                        <span className="text-gray-500 dark:text-gray-400 ml-2">
                          /{billingPeriod === "monthly" ? "mo" : "yr"}
                        </span>
                      )}
                    </div>
                    {billingPeriod === "yearly" && savings > 0 && (
                      <p className="text-green-600 dark:text-green-400 text-sm mt-1">
                        Save ${savings}/year
                      </p>
                    )}
                  </div>

                  {/* CTA Button */}
                  <button
                    onClick={() => handleSubscribe(plan.id)}
                    disabled={loadingPlan === plan.id || isCurrentPlan}
                    className={`w-full py-3 px-4 rounded-lg font-medium transition-colors mb-8 ${
                      isCurrentPlan
                        ? "bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-default"
                        : plan.highlighted
                        ? "bg-blue-600 text-white hover:bg-blue-700"
                        : "bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600"
                    }`}
                  >
                    {loadingPlan === plan.id
                      ? "Loading..."
                      : isCurrentPlan
                      ? "Current Plan"
                      : plan.cta}
                  </button>

                  {/* Features */}
                  <ul className="space-y-3">
                    {plan.features.map((feature, index) => (
                      <li key={index} className="flex items-start gap-3">
                        {feature.included ? (
                          <svg
                            className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M5 13l4 4L19 7"
                            />
                          </svg>
                        ) : (
                          <svg
                            className="w-5 h-5 text-gray-300 dark:text-gray-600 flex-shrink-0 mt-0.5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M6 18L18 6M6 6l12 12"
                            />
                          </svg>
                        )}
                        <span
                          className={
                            feature.included
                              ? "text-gray-700 dark:text-gray-300"
                              : "text-gray-400 dark:text-gray-500"
                          }
                        >
                          {feature.name}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>

        {/* FAQ or Additional Info */}
        <div className="mt-16 text-center">
          <p className="text-gray-600 dark:text-gray-400">
            Questions? Contact us at{" "}
            <a href="mailto:support@bidking.ai" className="text-blue-600 hover:underline">
              support@bidking.ai
            </a>
          </p>
        </div>
      </main>
    </div>
  );
}
