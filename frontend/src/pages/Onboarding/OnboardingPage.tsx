import { useState } from "react";
import { useNavigate } from "react-router";
import { useAuthStore } from "../../stores/authStore";
import { useProfileStore } from "../../stores/profileStore";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import Button from "../../components/ui/button/Button";
import toast from "react-hot-toast";

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { completeOnboarding, isLoading } = useProfileStore();

  const [formData, setFormData] = useState({
    first_name: "",
    last_name: "",
    phone: "",
    company_name: "",
    bio: "",
    country: "",
    city: "",
    state: "",
    postal_code: "",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.first_name || !formData.last_name) {
      toast.error("Please enter your first and last name");
      return;
    }

    if (!user?.id) {
      toast.error("User not found. Please log in again.");
      return;
    }

    try {
      await completeOnboarding(user.id, {
        ...formData,
        email: user.email,
      });
      toast.success("Profile setup complete!");
      navigate("/dashboard");
    } catch (err: any) {
      toast.error(err.message || "Failed to save profile");
    }
  };

  const handleSkip = () => {
    navigate("/dashboard");
  };

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
            Complete Your Profile
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Tell us a bit about yourself to get the most out of BidKing
          </p>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-6 sm:p-8">
          <form onSubmit={handleSubmit}>
            {/* Personal Information */}
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-gray-800 dark:text-white mb-4">
                Personal Information
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label>First Name <span className="text-red-500">*</span></Label>
                  <Input
                    type="text"
                    name="first_name"
                    placeholder="Enter your first name"
                    value={formData.first_name}
                    onChange={handleChange}
                  />
                </div>
                <div>
                  <Label>Last Name <span className="text-red-500">*</span></Label>
                  <Input
                    type="text"
                    name="last_name"
                    placeholder="Enter your last name"
                    value={formData.last_name}
                    onChange={handleChange}
                  />
                </div>
                <div>
                  <Label>Phone Number</Label>
                  <Input
                    type="tel"
                    name="phone"
                    placeholder="+1 (555) 123-4567"
                    value={formData.phone}
                    onChange={handleChange}
                  />
                </div>
                <div>
                  <Label>Company Name</Label>
                  <Input
                    type="text"
                    name="company_name"
                    placeholder="Your company or business name"
                    value={formData.company_name}
                    onChange={handleChange}
                  />
                </div>
                <div className="sm:col-span-2">
                  <Label>Bio / Role</Label>
                  <Input
                    type="text"
                    name="bio"
                    placeholder="e.g., Business Development Manager, Owner, etc."
                    value={formData.bio}
                    onChange={handleChange}
                  />
                </div>
              </div>
            </div>

            {/* Address Information */}
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-gray-800 dark:text-white mb-4">
                Location
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label>Country</Label>
                  <Input
                    type="text"
                    name="country"
                    placeholder="United States"
                    value={formData.country}
                    onChange={handleChange}
                  />
                </div>
                <div>
                  <Label>State</Label>
                  <Input
                    type="text"
                    name="state"
                    placeholder="California"
                    value={formData.state}
                    onChange={handleChange}
                  />
                </div>
                <div>
                  <Label>City</Label>
                  <Input
                    type="text"
                    name="city"
                    placeholder="San Francisco"
                    value={formData.city}
                    onChange={handleChange}
                  />
                </div>
                <div>
                  <Label>Postal Code</Label>
                  <Input
                    type="text"
                    name="postal_code"
                    placeholder="94102"
                    value={formData.postal_code}
                    onChange={handleChange}
                  />
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-3 sm:justify-between">
              <Button
                type="button"
                variant="outline"
                onClick={handleSkip}
                disabled={isLoading}
              >
                Skip for now
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading ? "Saving..." : "Complete Setup"}
              </Button>
            </div>
          </form>
        </div>

        <p className="text-center text-sm text-gray-500 dark:text-gray-400 mt-6">
          You can always update this information later in your profile settings.
        </p>
      </div>
    </div>
  );
}
