import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import PageMeta from "../../components/common/PageMeta";
import Button from "../../components/ui/button/Button";
import toast from "react-hot-toast";
import {
  getTemplates,
  getDefaultTemplates,
  createTemplate,
  deleteTemplate,
  generateQuickSection,
  ProposalTemplate,
  DefaultTemplate,
  TEMPLATE_TYPES,
  getTemplateTypeLabel,
} from "../../api/templates";

// Format date helper
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "Never";
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// Template type badge
function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    technical_approach: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    past_performance: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    management_approach: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
    executive_summary: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
    key_personnel: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400",
    price_cost: "bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-400",
  };

  return (
    <span className={`px-2 py-1 text-xs font-medium rounded ${colors[type] || "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"}`}>
      {getTemplateTypeLabel(type)}
    </span>
  );
}

// Template Card Component
function TemplateCard({
  template,
  onDelete,
  onGenerate,
  isDeleting,
}: {
  template: ProposalTemplate;
  onDelete: (id: string, name: string) => void;
  onGenerate: (template: ProposalTemplate) => void;
  isDeleting: boolean;
}) {
  return (
    <div className="p-5 bg-white rounded-lg border border-gray-200 dark:bg-gray-800 dark:border-gray-700 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-white">{template.name}</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {template.description || "No description"}
          </p>
        </div>
        <TypeBadge type={template.template_type} />
      </div>

      <div className="flex flex-wrap gap-2 mb-4 text-xs text-gray-500 dark:text-gray-400">
        {template.sections && template.sections.length > 0 && (
          <span>{template.sections.length} sections</span>
        )}
        <span>Used {template.times_used}x</span>
        {template.last_used_at && (
          <span>Last: {formatDate(template.last_used_at)}</span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="primary"
          onClick={() => onGenerate(template)}
          className="flex-1"
        >
          Generate Content
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onDelete(template.id, template.name)}
          disabled={isDeleting}
          className="text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
        >
          {isDeleting ? "..." : "Delete"}
        </Button>
      </div>
    </div>
  );
}

// Default Template Card (for copying)
function DefaultTemplateCard({
  template,
  onCopy,
  isCopying,
}: {
  template: DefaultTemplate;
  onCopy: (template: DefaultTemplate) => void;
  isCopying: boolean;
}) {
  return (
    <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 dark:bg-gray-700/50 dark:border-gray-600">
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-medium text-gray-900 dark:text-white">{template.name}</h4>
        <TypeBadge type={template.template_type} />
      </div>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
        {template.description}
      </p>
      <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">
        {template.sections.length} pre-defined sections
      </p>
      <Button
        size="sm"
        variant="outline"
        onClick={() => onCopy(template)}
        disabled={isCopying}
        className="w-full"
      >
        {isCopying ? "Copying..." : "Use This Template"}
      </Button>
    </div>
  );
}

// Quick Generate Modal
function QuickGenerateModal({
  isOpen,
  onClose,
  template,
}: {
  isOpen: boolean;
  onClose: () => void;
  template: ProposalTemplate | null;
}) {
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!template) return;

    setGenerating(true);
    setResult(null);

    try {
      const response = await generateQuickSection({
        template_type: template.template_type,
      });
      setResult(response.content);
      toast.success("Content generated successfully!");
    } catch {
      toast.error("Failed to generate content");
    } finally {
      setGenerating(false);
    }
  };

  if (!isOpen || !template) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="w-full max-w-3xl max-h-[90vh] overflow-auto bg-white rounded-xl shadow-2xl dark:bg-gray-800">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Generate: {template.name}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                AI-powered proposal section generation
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="p-6">
          {!result ? (
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                <svg className="w-8 h-8 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                Ready to Generate
              </h3>
              <p className="text-gray-500 dark:text-gray-400 mb-6 max-w-md mx-auto">
                Click the button below to generate a {getTemplateTypeLabel(template.template_type).toLowerCase()} section
                using your company profile and AI.
              </p>
              <Button
                onClick={handleGenerate}
                disabled={generating}
                className="px-8"
              >
                {generating ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Generating with AI...
                  </span>
                ) : (
                  "Generate Content"
                )}
              </Button>
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium text-gray-900 dark:text-white">Generated Content</h3>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    navigator.clipboard.writeText(result);
                    toast.success("Copied to clipboard!");
                  }}
                >
                  Copy
                </Button>
              </div>
              <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600 max-h-96 overflow-auto">
                <pre className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 font-sans">
                  {result}
                </pre>
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <Button variant="outline" onClick={() => setResult(null)}>
                  Generate Again
                </Button>
                <Button onClick={onClose}>Done</Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function TemplatesPage() {
  const queryClient = useQueryClient();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [copyingId, setCopyingId] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<ProposalTemplate | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);

  // Fetch user templates
  const {
    data: templates = [],
    isLoading: templatesLoading,
    error: templatesError,
  } = useQuery({
    queryKey: ["templates"],
    queryFn: () => getTemplates(),
  });

  // Fetch default templates
  const { data: defaultsData } = useQuery({
    queryKey: ["templates", "defaults"],
    queryFn: getDefaultTemplates,
  });

  const defaults = defaultsData?.defaults || [];

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      toast.success("Template deleted");
    },
    onError: () => {
      toast.error("Failed to delete template");
    },
  });

  // Create mutation (for copying defaults)
  const createMutation = useMutation({
    mutationFn: createTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      toast.success("Template created from default!");
    },
    onError: () => {
      toast.error("Failed to create template");
    },
  });

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to delete "${name}"?`)) return;
    setDeletingId(id);
    await deleteMutation.mutateAsync(id);
    setDeletingId(null);
  };

  const handleCopyDefault = async (defaultTemplate: DefaultTemplate) => {
    setCopyingId(defaultTemplate.id);
    await createMutation.mutateAsync({
      name: defaultTemplate.name,
      description: defaultTemplate.description,
      template_type: defaultTemplate.template_type,
      sections: defaultTemplate.sections,
    });
    setCopyingId(null);
  };

  const handleGenerate = (template: ProposalTemplate) => {
    setSelectedTemplate(template);
    setShowGenerateModal(true);
  };

  return (
    <>
      <PageMeta title="Proposal Templates | BidKing" description="AI-powered proposal template generator" />
      <PageBreadcrumb pageTitle="Proposal Templates" />

      <div className="space-y-8">
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            AI Proposal Templates
          </h2>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Generate professional proposal sections in seconds using AI
          </p>
        </div>

        {/* Error state */}
        {templatesError && (
          <div className="p-4 text-red-600 bg-red-50 rounded-lg dark:bg-red-900/20 dark:text-red-400">
            Failed to load templates
          </div>
        )}

        {/* User's Templates */}
        <section>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Your Templates
          </h3>

          {templatesLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-48 bg-gray-100 dark:bg-gray-700 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : templates.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700">
              <svg className="w-12 h-12 mx-auto text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-gray-500 dark:text-gray-400 mb-2">No templates yet</p>
              <p className="text-sm text-gray-400 dark:text-gray-500">
                Start by copying a default template below
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {templates.map((template) => (
                <TemplateCard
                  key={template.id}
                  template={template}
                  onDelete={handleDelete}
                  onGenerate={handleGenerate}
                  isDeleting={deletingId === template.id}
                />
              ))}
            </div>
          )}
        </section>

        {/* Default Templates */}
        <section>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            Default Templates
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Pre-built templates you can copy and customize
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {defaults.map((template) => (
              <DefaultTemplateCard
                key={template.id}
                template={template}
                onCopy={handleCopyDefault}
                isCopying={copyingId === template.id}
              />
            ))}
          </div>
        </section>

        {/* Quick Generate Section */}
        <section className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-full bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center flex-shrink-0">
              <svg className="w-6 h-6 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                Quick Generate
              </h3>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                Generate proposal content instantly without creating a template first.
                Just select a section type and let AI do the work.
              </p>
              <div className="flex flex-wrap gap-2">
                {TEMPLATE_TYPES.slice(0, 4).map((type) => (
                  <Button
                    key={type.value}
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setSelectedTemplate({
                        id: "quick",
                        name: type.label,
                        template_type: type.value,
                        use_company_profile: true,
                        use_past_performance: true,
                        use_capability_statement: true,
                        is_active: true,
                        is_default: false,
                        is_public: false,
                        times_used: 0,
                        created_at: "",
                        updated_at: "",
                      });
                      setShowGenerateModal(true);
                    }}
                  >
                    {type.label}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Generate Modal */}
      <QuickGenerateModal
        isOpen={showGenerateModal}
        onClose={() => {
          setShowGenerateModal(false);
          setSelectedTemplate(null);
        }}
        template={selectedTemplate}
      />
    </>
  );
}
