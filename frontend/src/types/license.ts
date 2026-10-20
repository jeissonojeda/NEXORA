export type LocalLicenseState =
  | 'NOT_ACTIVATED'
  | 'ACTIVE'
  | 'GRACE'
  | 'EXPIRED'
  | 'REVOKED'
  | 'INVALID'
  | 'CLOCK_ROLLBACK';

export interface LicenseStatus {
  status: LocalLicenseState;
  enforced: boolean;
  activated: boolean;
  message?: string | null;
  license_key?: string;
  license_type?: string;
  customer_name?: string | null;
  plan_code?: string | null;
  features?: string[];
  installation_id?: string;
  expires_at?: string | null;
  activated_at?: string | null;
  grace_days?: number;
  clock_rollback?: boolean;
}
