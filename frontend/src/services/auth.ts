import api from './api';
import type {
  AuthTokenResponse,
  AuthUser,
  LoginCredentials,
} from '../types/auth';

const TOKEN_STORAGE_KEY = 'token';

export function storeToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

function toFormData(credentials: LoginCredentials): URLSearchParams {
  const params = new URLSearchParams();
  params.append('username', credentials.username);
  params.append('password', credentials.password);
  return params;
}

export async function login(
  credentials: LoginCredentials
): Promise<AuthTokenResponse> {
  const response = await api.post<AuthTokenResponse>(
    '/auth/login',
    toFormData(credentials),
    {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }
  );
  storeToken(response.data.access_token);
  return response.data;
}

export async function getCurrentUser(): Promise<AuthUser> {
  const response = await api.get<AuthUser>('/auth/me');
  return response.data;
}

export async function logout(): Promise<void> {
  clearStoredToken();
}
