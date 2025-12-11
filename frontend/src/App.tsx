import { useEffect } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router";
import { Toaster } from "react-hot-toast";

// Landing page
import LandingPage from "./pages/Landing/LandingPage";

// Auth pages
import SignIn from "./pages/AuthPages/SignIn";
import SignUp from "./pages/AuthPages/SignUp";
import OnboardingPage from "./pages/Onboarding/OnboardingPage";

// Dashboard pages
import Home from "./pages/Dashboard/Home";
import UserProfiles from "./pages/UserProfiles";

// BidKing pages
import OpportunitiesList from "./pages/Opportunities/OpportunitiesList";
import OpportunityDetail from "./pages/Opportunities/OpportunityDetail";
import RecompetesList from "./pages/Recompetes/RecompetesList";
import RecompeteDetail from "./pages/Recompetes/RecompeteDetail";
import AlertProfilesList from "./pages/Alerts/AlertProfilesList";
import AlertProfileForm from "./pages/Alerts/AlertProfileForm";
import PipelinePage from "./pages/Pipeline/PipelinePage";

// Other pages
import NotFound from "./pages/OtherPage/NotFound";
import Calendar from "./pages/Calendar";
import Blank from "./pages/Blank";
import BasicTables from "./pages/Tables/BasicTables";
import FormElements from "./pages/Forms/FormElements";
import LineChart from "./pages/Charts/LineChart";
import BarChart from "./pages/Charts/BarChart";

// Layout
import AppLayout from "./layout/AppLayout";
import { ScrollToTop } from "./components/common/ScrollToTop";

// Auth store
import { useAuthStore } from "./stores/authStore";

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
        <Routes>
          {/* Public Landing Page */}
          <Route path="/" element={<LandingPage />} />

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

            {/* Alert Profiles */}
            <Route path="/alerts" element={<AlertProfilesList />} />
            <Route path="/alerts/create" element={<AlertProfileForm />} />
            <Route path="/alerts/:id/edit" element={<AlertProfileForm />} />

            {/* User Profile */}
            <Route path="/profile" element={<UserProfiles />} />

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

          {/* Fallback Route */}
          <Route path="*" element={<NotFound />} />
        </Routes>
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
