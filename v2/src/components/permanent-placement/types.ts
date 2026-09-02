export type Payment = {
  id: number;
  fee_type: string;
  amount_cents: number;
  status: string;
  paid_at?: string | null;
  paystack_reference?: string | null;
};

export type Invoice = {
  id: number;
  service_type: string;
  permanent_placement_id?: number | null;
  permanent_payment_id?: number | null;
  status: string;
  currency: string;
  subtotal_cents: number;
  vat_cents: number;
  total_cents: number;
  line_items: Array<{ description: string; amount_cents: number; fee_type?: string }>;
  invoice_number?: string | null;
  receipt_number?: string | null;
  invoice_pdf_url?: string | null;
  receipt_pdf_url?: string | null;
  issued_at?: string | null;
  paid_at?: string | null;
  invoice_email_requested_at?: string | null;
  receipt_email_requested_at?: string | null;
  created_at: string;
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
  interview_invite_status: string;
  interview_responded_at?: string | null;
  interview_credit_cycle?: number | null;
  interview_credit_consumed_at?: string | null;
  interview_credit_restored_at?: string | null;
  interview_checked_in_at?: string | null;
  interview_completed_at?: string | null;
  interview_format?: string | null;
  contact_window_open?: boolean;
  parent_contact_terms_accepted_at?: string | null;
  nanny_contact_terms_accepted_at?: string | null;
  contact_details_visible?: boolean;
  temporary_contact?: {
    name?: string | null;
    email?: string | null;
    phone?: string | null;
  } | null;
  trial_scheduled_at?: string | null;
  trial_ends_at?: string | null;
  trial_status?: string | null;
  trial_responded_at?: string | null;
  trial_alternative_at?: string | null;
  trial_notes?: string | null;
  offer_status?: string | null;
  offer_salary_cents?: number | null;
  offer_start_date?: string | null;
  offer_working_days?: number[];
  offer_start_time?: string | null;
  offer_end_time?: string | null;
  offer_terms?: string | null;
  offer_sent_at?: string | null;
  offer_responded_at?: string | null;
  availability_restructured_at?: string | null;
  parent_interview_decision?: string | null;
  parent_interview_feedback?: string | null;
  parent_interview_decided_at?: string | null;
  maybe_until?: string | null;
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
  replacement_count: number;
  upgraded_from_self_match: boolean;
  interview_credits: {
    cycle: number;
    included: number;
    used: number;
    available: number;
  };
  payments: Payment[];
  invoices: Invoice[];
  candidates?: Candidate[];
  parent_user_id?: number;
  parent_name?: string | null;
  parent_email?: string | null;
  parent_phone?: string | null;
  admin_notes?: string | null;
  pricing: Pricing;
  created_at: string;
};

export type Pricing = {
  currency: string;
  self_match: {
    activation_fee_cents: number;
    interview_package_fee_cents: number;
    candidate_access_fee_cents: number;
    success_fee_cents: number;
    total_if_placed_cents: number;
    profile_limit: number;
    interview_limit: number;
    candidate_access_days: number;
    replacement_days: number;
    replacement_credit_count: number;
    replacement_max_count: number;
    activation_fee_credits_toward_package: boolean;
  };
  concierge: {
    consultation_fee_cents: number;
    application_fee_cents: number;
    engagement_fee_cents: number;
    success_balance_cents: number;
    success_fee_cents: number;
    total_if_placed_cents: number;
    interview_limit: number;
    replacement_days: number;
  };
  rules: {
    maybe_period_days: number;
  };
  upgrade: {
    candidate_access_credit_cents: number;
    remaining_success_fee_cents: number;
  };
};

export type Config = { enabled: boolean; pricing: Pricing };

export type PermanentCommunication = {
  candidate_id: number;
  placement_id: number;
  window_open: boolean;
  locked_reason?: string | null;
  terms_text: string;
  viewer_role: "parent" | "nanny" | "admin";
  viewer_terms_accepted: boolean;
  parent_terms_accepted: boolean;
  nanny_terms_accepted: boolean;
  can_message: boolean;
  contact?: {
    name?: string | null;
    email?: string | null;
    phone?: string | null;
  } | null;
  messages: Array<{
    id: number;
    sender_user_id: number;
    sender_role: "parent" | "nanny" | "admin";
    sender_name: string;
    body: string;
    created_at: string;
  }>;
};

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
