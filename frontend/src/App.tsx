import { useEffect, lazy, Suspense } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router";
import { Toaster } from "react-hot-toast";

// Landing page - eagerly loaded (first page users see)
import LandingPage from "./pages/Landing/LandingPage";

// Auth pages - eagerly loaded (auth flow should be fast)
import SignIn from "./pages/AuthPages/SignIn";
import SignUp from "./pages/AuthPages/SignUp";

// Layout - eagerly loaded (common wrapper)
import AppLayout from "./layout/AppLayout";
import { ScrollToTop } from "./components/common/ScrollToTop";

// Auth store
import { useAuthStore } from "./stores/authStore";

// Lazy loaded pages - split into separate chunks
const Home = lazy(() => import("./pages/Dashboard/Home"));
const UserProfiles = lazy(() => import("./pages/UserProfiles"));
const OnboardingPage = lazy(() => import("./pages/Onboarding/OnboardingPage"));
const CompanyOnboardingPage = lazy(() => import("./pages/Onboarding/CompanyOnboardingPage"));

// BidKing pages - lazy loaded
const OpportunitiesList = lazy(() => import("./pages/Opportunities/OpportunitiesList"));
const OpportunityDetail = lazy(() => import("./pages/Opportunities/OpportunityDetail"));
const RecompetesList = lazy(() => import("./pages/Recompetes/RecompetesList"));
const RecompeteDetail = lazy(() => import("./pages/Recompetes/RecompeteDetail"));
const AlertProfilesList = lazy(() => import("./pages/Alerts/AlertProfilesList"));
const AlertProfileForm = lazy(() => import("./pages/Alerts/AlertProfileForm"));
const PipelinePage = lazy(() => import("./pages/Pipeline/PipelinePage"));
const AnalyticsPage = lazy(() => import("./pages/Analytics/AnalyticsPage"));
const TemplatesPage = lazy(() => import("./pages/Templates/TemplatesPage"));
const PricingPage = lazy(() => import("./pages/Pricing/PricingPage"));
const NotificationSettings = lazy(() => import("./pages/Settings/NotificationSettings"));

// Other pages - lazy loaded
const NotFound = lazy(() => import("./pages/OtherPage/NotFound"));
const Calendar = lazy(() => import("./pages/Calendar"));
const Blank = lazy(() => import("./pages/Blank"));
const BasicTables = lazy(() => import("./pages/Tables/BasicTables"));
const FormElements = lazy(() => import("./pages/Forms/FormElements"));
const LineChart = lazy(() => import("./pages/Charts/LineChart"));
const BarChart = lazy(() => import("./pages/Charts/BarChart"));

// Loading fallback component
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>
  );
}

export default function App() {
  const initialize = useAuthStore((state) => state.initialize);

  // Initialize Supabase auth on app mount
  useEffect(() => {
    initialize();
  }, [initialize]);
  return (
    <>
      <Router>
        <ScrollToTop />
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public Landing Page */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/pricing" element={<PricingPage />} />

            {/* Dashboard Layout */}
            <Route element={<AppLayout />}>
              {/* Main Dashboard */}
              <Route path="/dashboard" element={<Home />} />

              {/* Opportunities */}
              <Route path="/opportunities" element={<OpportunitiesList />} />
              <Route path="/opportunities/:id" element={<OpportunityDetail />} />

              {/* Recompetes */}
              <Route path="/recompetes" element={<RecompetesList />} />
              <Route path="/recompetes/:id" element={<RecompeteDetail />} />

              {/* Pipeline */}
              <Route path="/pipeline" element={<PipelinePage />} />

              {/* Analytics */}
              <Route path="/analytics" element={<AnalyticsPage />} />

              {/* Proposal Templates */}
              <Route path="/templates" element={<TemplatesPage />} />

              {/* Alert Profiles */}
              <Route path="/alerts" element={<AlertProfilesList />} />
              <Route path="/alerts/create" element={<AlertProfileForm />} />
              <Route path="/alerts/:id/edit" element={<AlertProfileForm />} />

              {/* User Profile */}
              <Route path="/profile" element={<UserProfiles />} />

              {/* Company Settings (edit mode - inside dashboard layout) */}
              <Route path="/settings/company" element={<CompanyOnboardingPage />} />

              {/* Notification Settings */}
              <Route path="/settings/notifications" element={<NotificationSettings />} />

              {/* Settings & Other */}
              <Route path="/calendar" element={<Calendar />} />
              <Route path="/blank" element={<Blank />} />
              <Route path="/form-elements" element={<FormElements />} />
              <Route path="/basic-tables" element={<BasicTables />} />
              <Route path="/line-chart" element={<LineChart />} />
              <Route path="/bar-chart" element={<BarChart />} />
            </Route>

            {/* Auth Layout */}
            <Route path="/signin" element={<SignIn />} />
            <Route path="/signup" element={<SignUp />} />
            <Route path="/onboarding" element={<OnboardingPage />} />
            <Route path="/company-setup" element={<CompanyOnboardingPage />} />

            {/* Fallback Route */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </Router>

      {/* Toast notifications */}
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: "#363636",
            color: "#fff",
          },
          success: {
            style: {
              background: "#10b981",
            },
          },
          error: {
            style: {
              background: "#ef4444",
            },
          },
        }}
      />
    </>
  );
}
