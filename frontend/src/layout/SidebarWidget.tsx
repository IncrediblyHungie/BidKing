import { Link } from "react-router";

export default function SidebarWidget() {
  return (
    <div
      className={`
        mx-auto mb-10 w-full max-w-60 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 px-4 py-5 text-center`}
    >
      <div className="mb-2 text-2xl">
        <svg className="w-8 h-8 mx-auto text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <h3 className="mb-2 font-semibold text-white">
        Upgrade to Pro
      </h3>
      <p className="mb-4 text-blue-100 text-theme-sm">
        Get unlimited alerts, real-time notifications & advanced filters.
      </p>
      <Link
        to="/signup"
        className="flex items-center justify-center p-3 font-medium text-blue-600 rounded-lg bg-white text-theme-sm hover:bg-blue-50 transition-colors"
      >
        Upgrade Now
      </Link>
    </div>
  );
}
