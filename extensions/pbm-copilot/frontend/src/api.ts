export interface CopilotSettings {
  baseUrl: string;
  token: string;
}

const SETTINGS_KEY = 'pbm.pbm-copilot.settings';

export function loadSettings(): CopilotSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        baseUrl: parsed.baseUrl || 'http://localhost:8000',
        token: parsed.token || '',
      };
    }
  } catch {
    // fall through to defaults
  }
  return { baseUrl: 'http://localhost:8000', token: '' };
}

export function saveSettings(settings: CopilotSettings): void {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

export interface ApiConfig {
  service: string;
  version: string;
  auth_required: boolean;
}

export interface Company {
  company_id: string;
  name: string;
  uploaded_at: string;
  record_count: number;
  status: string;
  dashboard_url: string | null;
}

export interface Metrics {
  claims_processed: number;
  anomalies: number;
  critical: number;
  high: number;
  avg_risk: number;
  total_paid: number;
}

export interface AnomalyRow {
  claim_id: string;
  claim_date: string;
  provider_id: string;
  plan_id: string;
  product_id: string;
  paid_amount: number;
  allowed_amount: number;
  risk_score: number;
  risk_level: string;
  rule_codes: string;
  evidence: string;
}

export interface UploadResult {
  status: string;
  company_id: string;
  rows_loaded: number;
  anomalies: number;
  risk_levels: Record<string, number>;
  dashboard_url: string | null;
}

export interface ExplainResult {
  claim_id: string;
  company_id: string;
  mode: string;
  risk_level: string;
  risk_score: number;
  provider_id: string;
  paid_amount: number;
  rule_codes: string;
  evidence: string;
  explanation: string;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { baseUrl, token } = loadSettings();
  const headers: Record<string, string> = {
    ...((init.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers['X-API-Token'] = token;
  }
  const res = await fetch(`${baseUrl.replace(/\/+$/, '')}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      // non-JSON error body
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const getConfig = () => apiFetch<ApiConfig>('/api/config');
export const getMetrics = () => apiFetch<Metrics>('/metrics');
export const getCompanies = () => apiFetch<Company[]>('/api/companies');
export const getAnomalies = (limit = 25) =>
  apiFetch<AnomalyRow[]>(`/anomalies?limit=${limit}`);

export function explainClaim(claimId: string, companyId?: string) {
  const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : '';
  return apiFetch<ExplainResult>(`/explain/${encodeURIComponent(claimId)}${qs}`, {
    method: 'POST',
  });
}

export async function uploadClaims(
  companyName: string,
  file: File,
): Promise<UploadResult> {
  const body = new FormData();
  body.append('company_name', companyName);
  body.append('file', file);
  return apiFetch<UploadResult>('/api/upload', { method: 'POST', body });
}