export const ROUTES = {
  HOME: '/',
} as const;

export type RoutePath = (typeof ROUTES)[keyof typeof ROUTES];
