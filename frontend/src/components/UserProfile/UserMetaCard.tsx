import { useAuthStore } from "../../stores/authStore";
import { useProfileStore } from "../../stores/profileStore";

export default function UserMetaCard() {
  const { user } = useAuthStore();
  const { profile } = useProfileStore();

  const displayName = profile?.first_name && profile?.last_name
    ? `${profile.first_name} ${profile.last_name}`
    : user?.email || "User";

  const location = profile?.city && profile?.state
    ? `${profile.city}, ${profile.state}`
    : profile?.country || "Location not set";

  // Get initials from first and last name, or first letter of email
  const getInitials = () => {
    if (profile?.first_name && profile?.last_name) {
      return `${profile.first_name.charAt(0)}${profile.last_name.charAt(0)}`.toUpperCase();
    }
    if (profile?.first_name) {
      return profile.first_name.charAt(0).toUpperCase();
    }
    // For email, get the first letter that's not a number
    const email = user?.email || '';
    const firstLetter = email.split('').find(char => /[a-zA-Z]/.test(char));
    return firstLetter?.toUpperCase() || 'U';
  };

  const initials = getInitials();

  return (
    <div className="p-5 border border-gray-200 rounded-2xl dark:border-gray-800 lg:p-6">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-col items-center w-full gap-6 xl:flex-row">
          <div className="w-20 h-20 overflow-hidden border border-gray-200 rounded-full dark:border-gray-800 bg-brand-500 flex items-center justify-center">
            <span className="text-2xl font-bold text-white">
              {initials}
            </span>
          </div>
          <div className="order-3 xl:order-2">
            <h4 className="mb-2 text-lg font-semibold text-center text-gray-800 dark:text-white/90 xl:text-left">
              {displayName}
            </h4>
            <div className="flex flex-col items-center gap-1 text-center xl:flex-row xl:gap-3 xl:text-left">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {profile?.bio || profile?.company_name || "No bio set"}
              </p>
              <div className="hidden h-3.5 w-px bg-gray-300 dark:bg-gray-700 xl:block"></div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {location}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
