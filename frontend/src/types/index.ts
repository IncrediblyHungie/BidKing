/**
 * TypeScript types for BidKing API
 */

// User types
export interface User {
  id: string;
  email: string;
  company_name: string | null;
  subscription_tier: 'free' | 'starter' | 'pro';
  is_verified: boolean;
  created_at: string;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface UserRegister {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// Alert Profile types
export interface AlertProfile {
  id: string;
  user_id: string;
  name: string;
  naics_codes: string[];
  psc_codes: string[];
  keywords: string[];
  excluded_keywords: string[];
  agencies: string[];
  states: string[];
  set_aside_types: string[];
  min_likelihood_score: number;
  alert_frequency: 'realtime' | 'daily' | 'weekly';
  is_active: boolean;
  last_alert_sent: string | null;
  match_count: number;
  created_at: string;
  updated_at: string;
}

export interface AlertProfileCreate {
  name: string;
  naics_codes?: string[];
  psc_codes?: string[];
  keywords?: string[];
  excluded_keywords?: string[];
  agencies?: string[];
  states?: string[];
  set_aside_types?: string[];
  min_likelihood_score?: number;
  alert_frequency?: 'realtime' | 'daily' | 'weekly';
  is_active?: boolean;
}

// Opportunity types
export interface PointOfContact {
  name: string | null;
  email: string | null;
  phone: string | null;
  title: string | null;
  type: string | null;
}

export interface Opportunity {
  id: string;
  notice_id: string;
  solicitation_number: string | null;
  title: string;
  description: string | null;
  posted_date: string | null;
  response_deadline: string | null;
  archive_date: string | null;
  type: string | null;
  type_description: string | null;
  naics_code: string | null;
  naics_description: string | null;
  psc_code: string | null;
  psc_description: string | null;
  agency_name: string | null;
  sub_agency_name: string | null;
  office_name: string | null;
  pop_city: string | null;
  pop_state: string | null;
  pop_zip: string | null;
  pop_country: string | null;
  set_aside_type: string | null;
  set_aside_description: string | null;
  likelihood_score: number;
  sam_gov_link: string | null;
  points_of_contact: PointOfContact[];
}

export interface OpportunityListResponse {
  items: Opportunity[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface OpportunitySearchParams {
  query?: string;
  naics_codes?: string[];
  states?: string[];
  agencies?: string[];
  set_aside_types?: string[];
  min_score?: number;
  max_score?: number;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface OpportunityFilters {
  keywords?: string;
  naics_codes?: string[];
  set_aside?: string;
  state?: string;
  posted_from?: string;
  posted_to?: string;
  response_deadline_from?: string;
  response_deadline_to?: string;
  min_score?: number;
  status?: 'active' | 'inactive' | 'all';
  page?: number;
  page_size?: number;
}

// Market Intelligence types
export interface NAICSStatistics {
  naics_code: string;
  naics_description: string | null;
  total_awards_12mo: number;
  total_obligation_12mo: string;
  avg_award_amount_12mo: string;
  median_award_amount_12mo: string;
  awards_under_25k: number;
  awards_25k_to_100k: number;
  awards_100k_to_250k: number;
  awards_250k_to_1m: number;
  awards_over_1m: number;
  small_business_awards: number;
  small_business_percentage: string;
  top_agencies: { name: string; count: number }[];
  top_recipients: { name: string; count: number }[];
  calculated_at: string;
}

export interface LaborRate {
  search_query: string;
  experience_range: string | null;
  education_level: string | null;
  match_count: number;
  min_rate: string | null;
  max_rate: string | null;
  avg_rate: string | null;
  median_rate: string | null;
  percentile_25: string | null;
  percentile_75: string | null;
  sample_categories: { name: string; count: number; avg_rate: string }[];
  cached_at: string;
  data_freshness: string;
}

export interface Recompete {
  id: string;
  award_id: string;
  piid: string;
  period_of_performance_end: string;
  days_until_expiration: number;
  naics_code: string | null;
  total_value: string | null;
  awarding_agency_name: string | null;
  incumbent_name: string | null;
  incumbent_uei: string | null;
  status: string;
  linked_opportunity_id: string | null;
  created_at: string;
  updated_at: string;
}

// Subscription types
export interface Subscription {
  id: string;
  user_id: string;
  tier: string;
  status: string;
  stripe_subscription_id: string | null;
  stripe_customer_id: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionTier {
  tier: string;
  price_monthly: number;
  price_yearly: number;
  limits: {
    alert_profiles: number;
    alerts_per_month: number;
    api_calls_per_hour: number;
    realtime_alerts?: boolean;
    market_intelligence?: boolean;
    recompete_tracking?: boolean;
  };
  features: string[];
}

export interface Usage {
  user_id: string;
  period_start: string;
  period_end: string;
  alerts_sent: number;
  api_calls: number;
  opportunities_viewed: number;
  exports_count: number;
  alerts_limit: number;
  api_calls_limit: number;
  exports_limit: number;
  alerts_usage_percent: number;
  api_usage_percent: number;
}

// Dashboard stats
export interface OpportunityStats {
  total_active: number;
  new_today: number;
  score_distribution: {
    high: number;
    medium: number;
    low: number;
  };
  top_agencies: { name: string; count: number }[];
  top_naics: { code: string; count: number }[];
  generated_at: string;
}

export interface MarketOverview {
  total_active_opportunities: number;
  new_opportunities_today: number;
  new_opportunities_week: number;
  opportunities_by_type: Record<string, number>;
  opportunities_by_setaside: Record<string, number>;
  top_agencies: { name: string; count: number }[];
  contracts_expiring_30_days: number;
  contracts_expiring_90_days: number;
  high_score_opportunities: number;
  medium_score_opportunities: number;
  low_score_opportunities: number;
  generated_at: string;
}
