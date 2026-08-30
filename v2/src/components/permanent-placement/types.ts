export type Payment = {
  id: number;
  fee_type: string;
  amount_cents: number;
  status: string;
  paid_at?: string | null;
  paystack_reference?: string | null;
};

export type Candidate = {
  id: number;
  candidate_code: string;
  nanny_id: number;
  status: string;
  consent_status: string;
  first_name: string;
  full_name?: string | null;
  email?: string | null;
  phone?: string | null;
  profile_photo_url?: string | null;
  broad_location?: string | null;
  bio?: string | null;
  experience_count: number;
  qualifications: string[];
  languages: string[];
  desired_salary_min_cents?: number | null;
  desired_salary_max_cents?: number | null;
  verification: Record<string, boolean | number>;
  interview_scheduled_at?: string | null;
  interview_format?: string | null;
  trial_scheduled_at?: string | null;
  profile_released_at?: string | null;
};

export type Placement = {
  id: number;
  service_tier: "self_match" | "concierge";
  status: string;
  role_title: string;
  employment_type: string;
  start_date?: string | null;
  schedule_summary: string;
  hours_per_week?: number | null;
  children_count: number;
  children_ages: string[];
  duties: string;
  special_requirements?: string | null;
  salary_min_cents: number;
  salary_max_cents: number;
  location_suburb: string;
  location_city: string;
  location_province?: string | null;
  live_in: boolean;
  drivers_license_required: boolean;
  own_car_required: boolean;
  languages: string[];
  pets?: string | null;
  parent_notes?: string | null;
  candidate_access_expires_at?: string | null;
  placed_nanny_id?: number | null;
  hired_at?: string | null;
  success_fee_due_at?: string | null;
  guarantee_until?: string | null;
  replacement_status: string;
  replacement_requested_at?: string | null;
  replacement_reason?: string | null;
  upgraded_from_self_match: boolean;
  payments: Payment[];
  candidates?: Candidate[];
  parent_user_id?: number;
  parent_name?: string | null;
  parent_email?: string | null;
  parent_phone?: string | null;
  admin_notes?: string | null;
  created_at: string;
};

export type Pricing = {
  self_match: {
    activation_fee_cents: number;
    candidate_access_fee_cents: number;
    success_fee_cents: number;
    total_if_placed_cents: number;
    profile_limit: number;
    interview_limit: number;
    candidate_access_days: number;
    rematch_days: number;
  };
  concierge: {
    application_fee_cents: number;
    success_fee_cents: number;
    total_if_placed_cents: number;
    interview_limit: number;
    replacement_days: number;
  };
  upgrade: {
    candidate_access_credit_cents: number;
    remaining_success_fee_cents: number;
  };
};

export type Config = { enabled: boolean; pricing: Pricing };

export function money(cents?: number | null) {
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
    maximumFractionDigits: 0,
  }).format((cents || 0) / 100);
}

export function niceStatus(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function dateTime(value?: string | null) {
  if (!value) return "Not scheduled";
  return new Date(value).toLocaleString("en-ZA", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
