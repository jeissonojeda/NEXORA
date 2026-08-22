export interface LoginCredentials {
  username: string;
  password: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
}

export interface AuthRole {
  name: string;
  display_name: string;
}

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  roles: AuthRole[];
}

export function hasRole(user: AuthUser, ...roleNames: string[]): boolean {
  return user.roles.some((role) => roleNames.includes(role.name));
}

export function isAdmin(user: AuthUser): boolean {
  return hasRole(user, 'ADMIN');
}
