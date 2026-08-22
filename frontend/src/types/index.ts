export interface HealthStatus {
  status: string;
  database: string;
  environment: string;
}

export interface ApiInfo {
  name: string;
  version: string;
  environment: string;
}
