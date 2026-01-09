import { useEffect, useState } from "react";
import { Link } from "react-router";
import { opportunitiesApi } from "../../api";
import { supabase } from "../../lib/supabase";
import { SavedOpportunity, PipelineStatus, SavedOpportunityUpdate } from "../../types";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";

// Pipeline stages configuration
const PIPELINE_STAGES: { key: PipelineStatus; label: string; color: string; bgColor: string }[] = [
  { key: "watching", label: "Watching", color: "text-blue-700", bgColor: "bg-blue-50 dark:bg-blue-900/20" },
  { key: "researching", label: "Researching", color: "text-purple-700", bgColor: "bg-purple-50 dark:bg-purple-900/20" },
  { key: "preparing", label: "Preparing", color: "text-yellow-700", bgColor: "bg-yellow-50 dark:bg-yellow-900/20" },
  { key: "submitted", label: "Submitted", color: "text-orange-700", bgColor: "bg-orange-50 dark:bg-orange-900/20" },
  { key: "won", label: "Won", color: "text-green-700", bgColor: "bg-green-50 dark:bg-green-900/20" },
  { key: "lost", label: "Lost", color: "text-red-700", bgColor: "bg-red-50 dark:bg-red-900/20" },
];

// Format date helper
function formatDate(dateString: string | null): string {
  if (!dateString) return "No deadline";
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// Days until deadline
function getDaysUntil(dateString: string | null): { text: string; urgent: boolean } {
  if (!dateString) return { text: "", urgent: false };
  const now = new Date();
  const deadline = new Date(dateString);
  const diffTime = deadline.getTime() - now.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return { text: "Expired", urgent: true };
  if (diffDays === 0) return { text: "Today!", urgent: true };
  if (diffDays === 1) return { text: "Tomorrow", urgent: true };
  if (diffDays <= 7) return { text: `${diffDays} days`, urgent: true };
  return { text: `${diffDays} days`, urgent: false };
}

// Priority badge
function PriorityBadge({ priority }: { priority: number }) {
  const colors: Record<number, string> = {
    1: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    2: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
    3: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300",
    4: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    5: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  };
  const labels: Record<number, string> = {
    1: "Critical",
    2: "High",
    3: "Medium",
    4: "Low",
    5: "Someday",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${colors[priority] || colors[3]}`}>
      {labels[priority] || "Medium"}
    </span>
  );
}

// Opportunity Card Component
function OpportunityCard({
  saved,
  onMoveStage,
  onEdit,
  onDelete,
}: {
  saved: SavedOpportunity;
  onMoveStage: (savedId: string, newStatus: PipelineStatus) => void;
  onEdit: (saved: SavedOpportunity) => void;
  onDelete: (savedId: string) => void;
}) {
  const opp = saved.opportunity;
  const deadline = getDaysUntil(opp.response_deadline);

  return (
    <div className="p-3 mb-2 bg-white rounded-lg shadow-sm border border-gray-200 dark:bg-gray-800 dark:border-gray-700 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <Link
          to={`/opportunities/${opp.id}`}
          className="text-sm font-medium text-gray-900 dark:text-white hover:text-brand-500 line-clamp-2"
        >
          {opp.title}
        </Link>
        <PriorityBadge priority={saved.priority} />
      </div>

      {/* Agency */}
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-2 truncate">
        {opp.agency_name || "Unknown Agency"}
      </p>

      {/* Deadline */}
      {opp.response_deadline && (
        <div className={`text-xs mb-2 ${deadline.urgent ? "text-red-600 font-medium" : "text-gray-500"}`}>
          Deadline: {formatDate(opp.response_deadline)}
          {deadline.text && <span className="ml-1">({deadline.text})</span>}
        </div>
      )}

      {/* Notes preview */}
      {saved.notes && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-2 line-clamp-2 italic">
          "{saved.notes}"
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-gray-700">
        <select
          value={saved.status}
          onChange={(e) => onMoveStage(saved.id, e.target.value as PipelineStatus)}
          className="text-xs border rounded px-2 py-1 dark:bg-gray-700 dark:border-gray-600"
        >
          {PIPELINE_STAGES.map((stage) => (
            <option key={stage.key} value={stage.key}>
              → {stage.label}
            </option>
          ))}
          <option value="archived">→ Archive</option>
        </select>
        <div className="flex gap-2">
          <button
            onClick={() => onEdit(saved)}
            className="text-xs text-brand-500 hover:text-brand-600"
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(saved.id)}
            className="text-xs text-red-500 hover:text-red-600"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// Edit Modal Component
function EditModal({
  saved,
  onClose,
  onSave,
}: {
  saved: SavedOpportunity;
  onClose: () => void;
  onSave: (savedId: string, data: SavedOpportunityUpdate) => void;
}) {
  const [notes, setNotes] = useState(saved.notes || "");
  const [priority, setPriority] = useState(saved.priority);
  const [reminderDate, setReminderDate] = useState(saved.reminder_date || "");
  const [status, setStatus] = useState(saved.status);
  // Win tracking
  const [winAmount, setWinAmount] = useState(saved.win_amount?.toString() || "");
  const [winDate, setWinDate] = useState(saved.win_date || "");
  // Loss tracking
  const [winnerName, setWinnerName] = useState(saved.winner_name || "");
  const [lossReason, setLossReason] = useState(saved.loss_reason || "");
  // Feedback
  const [feedbackNotes, setFeedbackNotes] = useState(saved.feedback_notes || "");

  const handleSave = () => {
    const data: SavedOpportunityUpdate = {
      notes,
      priority,
      reminder_date: reminderDate || undefined,
      status,
    };
    // Add win tracking fields if won
    if (status === "won") {
      data.win_amount = winAmount ? parseFloat(winAmount) : undefined;
      data.win_date = winDate || undefined;
      data.feedback_notes = feedbackNotes || undefined;
    }
    // Add loss tracking fields if lost
    if (status === "lost") {
      data.winner_name = winnerName || undefined;
      data.loss_reason = lossReason || undefined;
      data.feedback_notes = feedbackNotes || undefined;
    }
    onSave(saved.id, data);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg p-6 bg-white rounded-lg dark:bg-gray-800 max-h-[90vh] overflow-y-auto">
        <h3 className="text-lg font-semibold mb-4 dark:text-white">Edit Pipeline Item</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">{saved.opportunity.title}</p>

        {/* Status */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1 dark:text-gray-200">Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as PipelineStatus)}
            className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
          >
            {PIPELINE_STAGES.map((stage) => (
              <option key={stage.key} value={stage.key}>
                {stage.label}
              </option>
            ))}
            <option value="archived">Archived</option>
          </select>
        </div>

        {/* Win Fields - Only show when status is "won" */}
        {status === "won" && (
          <div className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
            <h4 className="text-sm font-semibold text-green-700 dark:text-green-400 mb-3">Win Details</h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-gray-200">Win Amount ($)</label>
                <input
                  type="number"
                  value={winAmount}
                  onChange={(e) => setWinAmount(e.target.value)}
                  placeholder="Contract value"
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-gray-200">Win Date</label>
                <input
                  type="date"
                  value={winDate}
                  onChange={(e) => setWinDate(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                />
              </div>
            </div>
          </div>
        )}

        {/* Loss Fields - Only show when status is "lost" */}
        {status === "lost" && (
          <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
            <h4 className="text-sm font-semibold text-red-700 dark:text-red-400 mb-3">Loss Details</h4>
            <div className="mb-3">
              <label className="block text-sm font-medium mb-1 dark:text-gray-200">Winner Name</label>
              <input
                type="text"
                value={winnerName}
                onChange={(e) => setWinnerName(e.target.value)}
                placeholder="Who won this contract?"
                className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1 dark:text-gray-200">Loss Reason</label>
              <textarea
                value={lossReason}
                onChange={(e) => setLossReason(e.target.value)}
                rows={2}
                placeholder="Why did we lose? (price, experience, etc.)"
                className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
          </div>
        )}

        {/* Feedback Notes - Show for both won and lost */}
        {(status === "won" || status === "lost") && (
          <div className="mb-4">
            <label className="block text-sm font-medium mb-1 dark:text-gray-200">
              Lessons Learned
            </label>
            <textarea
              value={feedbackNotes}
              onChange={(e) => setFeedbackNotes(e.target.value)}
              rows={3}
              placeholder="What did you learn from this opportunity? What would you do differently?"
              className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
            />
          </div>
        )}

        {/* Priority */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1 dark:text-gray-200">Priority</label>
          <select
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value))}
            className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
          >
            <option value={1}>1 - Critical</option>
            <option value={2}>2 - High</option>
            <option value={3}>3 - Medium</option>
            <option value={4}>4 - Low</option>
            <option value={5}>5 - Someday</option>
          </select>
        </div>

        {/* Reminder Date */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1 dark:text-gray-200">Reminder Date</label>
          <input
            type="date"
            value={reminderDate}
            onChange={(e) => setReminderDate(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
          />
        </div>

        {/* Notes */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1 dark:text-gray-200">Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={4}
            placeholder="Add your notes about this opportunity..."
            className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
          />
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 text-sm text-white bg-brand-500 rounded-lg hover:bg-brand-600"
          >
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PipelinePage() {
  const [savedOpportunities, setSavedOpportunities] = useState<SavedOpportunity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<SavedOpportunity | null>(null);
  const [viewMode, setViewMode] = useState<"kanban" | "list">("kanban");

  useEffect(() => {
    fetchSavedOpportunities();
  }, []);

  const fetchSavedOpportunities = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await opportunitiesApi.listSaved();
      setSavedOpportunities(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to fetch pipeline");
    } finally {
      setIsLoading(false);
    }
  };

  const handleMoveStage = async (savedId: string, newStatus: PipelineStatus) => {
    try {
      await opportunitiesApi.updateSaved(savedId, { status: newStatus });
      setSavedOpportunities((prev) =>
        prev.map((item) =>
          item.id === savedId ? { ...item, status: newStatus } : item
        )
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to update status");
    }
  };

  const handleSaveEdit = async (savedId: string, data: SavedOpportunityUpdate) => {
    try {
      const updated = await opportunitiesApi.updateSaved(savedId, data);
      setSavedOpportunities((prev) =>
        prev.map((item) => (item.id === savedId ? updated : item))
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to update");
    }
  };

  const handleDelete = async (savedId: string) => {
    if (!window.confirm("Are you sure you want to delete this opportunity from your pipeline? This cannot be undone.")) {
      return;
    }
    try {
      await opportunitiesApi.unsave(savedId);
      setSavedOpportunities((prev) => prev.filter((item) => item.id !== savedId));
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to delete");
    }
  };

  const handleExportCSV = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        setError("You must be logged in to export pipeline data");
        return;
      }

      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "https://api.bidking.ai"}/api/v1/opportunities/saved/export/csv`,
        {
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
        }
      );

      if (!response.ok) throw new Error("Export failed");

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `bidking_pipeline_${new Date().toISOString().split("T")[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error("Export error:", err);
      setError("Failed to export CSV");
    }
  };

  // Group by status for kanban view
  const groupedByStatus = PIPELINE_STAGES.reduce((acc, stage) => {
    acc[stage.key] = savedOpportunities.filter(
      (item) => item.status === stage.key
    );
    return acc;
  }, {} as Record<PipelineStatus, SavedOpportunity[]>);

  // Stats
  const totalActive = savedOpportunities.filter(
    (item) => !["won", "lost", "archived"].includes(item.status)
  ).length;
  const urgentDeadlines = savedOpportunities.filter((item) => {
    if (!item.opportunity.response_deadline) return false;
    const days = getDaysUntil(item.opportunity.response_deadline);
    return days.urgent && !["won", "lost", "archived"].includes(item.status);
  }).length;

  return (
    <>
      <PageMeta title="Pipeline | BidKing" description="Track your opportunities" />
      <PageBreadcrumb pageTitle="Pipeline" />

      <div className="space-y-6">
        {/* Header Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <p className="text-sm text-gray-500 dark:text-gray-400">Total in Pipeline</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{savedOpportunities.length}</p>
          </div>
          <div className="p-4 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <p className="text-sm text-gray-500 dark:text-gray-400">Active</p>
            <p className="text-2xl font-bold text-blue-600">{totalActive}</p>
          </div>
          <div className="p-4 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <p className="text-sm text-gray-500 dark:text-gray-400">Urgent Deadlines</p>
            <p className="text-2xl font-bold text-red-600">{urgentDeadlines}</p>
          </div>
          <div className="p-4 bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <p className="text-sm text-gray-500 dark:text-gray-400">Won</p>
            <p className="text-2xl font-bold text-green-600">
              {savedOpportunities.filter((i) => i.status === "won").length}
            </p>
          </div>
        </div>

        {/* View Toggle */}
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Drag opportunities between stages or use the dropdown to move them.
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleExportCSV}
              className="px-3 py-1 text-sm rounded bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Export CSV
            </button>
            <button
              onClick={() => setViewMode("kanban")}
              className={`px-3 py-1 text-sm rounded ${
                viewMode === "kanban"
                  ? "bg-brand-500 text-white"
                  : "bg-gray-100 dark:bg-gray-700"
              }`}
            >
              Kanban
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`px-3 py-1 text-sm rounded ${
                viewMode === "list"
                  ? "bg-brand-500 text-white"
                  : "bg-gray-100 dark:bg-gray-700"
              }`}
            >
              List
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="p-4 text-red-600 bg-red-50 rounded-lg dark:bg-red-900/20">
            {error}
          </div>
        )}

        {/* Loading */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-4 border-blue-500 rounded-full animate-spin border-t-transparent"></div>
          </div>
        ) : savedOpportunities.length === 0 ? (
          <div className="p-12 text-center bg-white rounded-lg shadow-sm dark:bg-gray-800">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              Your pipeline is empty
            </h3>
            <p className="text-gray-500 dark:text-gray-400 mb-4">
              Save opportunities from the Opportunities page to track them here.
            </p>
            <Link
              to="/opportunities"
              className="inline-block px-4 py-2 text-sm text-white bg-brand-500 rounded-lg hover:bg-brand-600"
            >
              Browse Opportunities
            </Link>
          </div>
        ) : viewMode === "kanban" ? (
          /* Kanban View */
          <div className="flex gap-4 overflow-x-auto pb-4">
            {PIPELINE_STAGES.map((stage) => (
              <div
                key={stage.key}
                className={`flex-shrink-0 w-72 rounded-lg ${stage.bgColor}`}
              >
                {/* Stage Header */}
                <div className="p-3 border-b border-gray-200 dark:border-gray-700">
                  <div className="flex items-center justify-between">
                    <h3 className={`font-medium ${stage.color}`}>{stage.label}</h3>
                    <span className="text-xs text-gray-500 bg-white dark:bg-gray-700 px-2 py-0.5 rounded-full">
                      {groupedByStatus[stage.key]?.length || 0}
                    </span>
                  </div>
                </div>

                {/* Stage Cards */}
                <div className="p-2 min-h-[200px]">
                  {groupedByStatus[stage.key]?.map((saved) => (
                    <OpportunityCard
                      key={saved.id}
                      saved={saved}
                      onMoveStage={handleMoveStage}
                      onEdit={setEditingItem}
                      onDelete={handleDelete}
                    />
                  ))}
                  {groupedByStatus[stage.key]?.length === 0 && (
                    <p className="text-xs text-gray-400 text-center py-8">
                      No opportunities
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* List View */
          <div className="bg-white rounded-lg shadow-sm dark:bg-gray-800 overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Opportunity
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Priority
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Deadline
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {savedOpportunities.map((saved) => {
                  const deadline = getDaysUntil(saved.opportunity.response_deadline);
                  return (
                    <tr key={saved.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                      <td className="px-4 py-3">
                        <Link
                          to={`/opportunities/${saved.opportunity.id}`}
                          className="text-sm font-medium text-gray-900 dark:text-white hover:text-brand-500"
                        >
                          {saved.opportunity.title}
                        </Link>
                        <p className="text-xs text-gray-500">{saved.opportunity.agency_name}</p>
                      </td>
                      <td className="px-4 py-3">
                        <select
                          value={saved.status}
                          onChange={(e) => handleMoveStage(saved.id, e.target.value as PipelineStatus)}
                          className="text-xs border rounded px-2 py-1 dark:bg-gray-700 dark:border-gray-600"
                        >
                          {PIPELINE_STAGES.map((stage) => (
                            <option key={stage.key} value={stage.key}>
                              {stage.label}
                            </option>
                          ))}
                          <option value="archived">Archived</option>
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <PriorityBadge priority={saved.priority} />
                      </td>
                      <td className="px-4 py-3">
                        <span className={deadline.urgent ? "text-red-600 font-medium text-sm" : "text-sm text-gray-600"}>
                          {formatDate(saved.opportunity.response_deadline)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-3">
                          <button
                            onClick={() => setEditingItem(saved)}
                            className="text-sm text-brand-500 hover:text-brand-600"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleDelete(saved.id)}
                            className="text-sm text-red-500 hover:text-red-600"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {editingItem && (
        <EditModal
          saved={editingItem}
          onClose={() => setEditingItem(null)}
          onSave={handleSaveEdit}
        />
      )}
    </>
  );
}
