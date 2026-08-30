import { useEffect, useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { ROUTES } from '../routes';
import { userHasPermission } from '../utils/permissions';
import Icon from '../components/ui/Icon';
import type { IconName } from '../components/ui/Icon';
import ThemeToggle from '../components/ui/ThemeToggle';

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  permission?: string;
  end?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: 'Principal',
    items: [{ to: ROUTES.HOME, label: 'Inicio', icon: 'home', end: true }],
  },
  {
    title: 'Comercial',
    items: [
      {
        to: ROUTES.POS,
        label: 'Punto de venta',
        icon: 'bag',
        permission: 'sales.create',
      },
      {
        to: ROUTES.SALES,
        label: 'Ventas',
        icon: 'receipt',
        permission: 'sales.read',
      },
    ],
  },
  {
    title: 'Catálogo',
    items: [
      {
        to: ROUTES.PRODUCTS,
        label: 'Productos',
        icon: 'package',
        permission: 'products.read',
      },
      {
        to: ROUTES.CATEGORIES,
        label: 'Categorías',
        icon: 'tag',
        permission: 'categories.read',
      },
    ],
  },
  {
    title: 'Almacén',
    items: [
      {
        to: ROUTES.INVENTORY,
        label: 'Inventario',
        icon: 'layers',
        permission: 'inventory.read',
      },
      {
        to: ROUTES.PURCHASES,
        label: 'Compras',
        icon: 'truck',
        permission: 'purchases.read',
      },
      {
        to: ROUTES.SUPPLIERS,
        label: 'Proveedores',
        icon: 'store',
        permission: 'suppliers.read',
      },
    ],
  },
  {
    title: 'Clientes',
    items: [
      {
        to: ROUTES.CUSTOMERS,
        label: 'Clientes',
        icon: 'users',
        permission: 'customers.read',
      },
      {
        to: ROUTES.RECEIVABLES,
        label: 'Cuentas por cobrar',
        icon: 'banknote',
        permission: 'receivables.read',
      },
    ],
  },
  {
    title: 'Operaciones',
    items: [
      {
        to: ROUTES.CASH,
        label: 'Caja',
        icon: 'wallet',
        permission: 'cash.read',
      },
      {
        to: ROUTES.REPORTS,
        label: 'Reportes',
        icon: 'chart-bar',
        permission: 'reports.read',
      },
      {
        to: ROUTES.AI,
        label: 'NEXORA IA',
        icon: 'sparkles',
        permission: 'ai.read',
      },
    ],
  },
];

function brandMark(collapsed: boolean) {
  return (
    <div
      className={`flex items-center gap-2.5 ${collapsed ? 'justify-center px-0' : 'px-4'}`}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl nx-brand-gradient text-white shadow-md">
        <Icon name="sparkles" size={19} />
      </span>
      {!collapsed && (
        <span className="leading-tight">
          <span className="block text-base font-extrabold tracking-tight text-foreground">
            NEXORA
          </span>
          <span className="block text-[10px] font-medium text-faint">
            Gestión inteligente
          </span>
        </span>
      )}
    </div>
  );
}

interface SidebarContentProps {
  collapsed: boolean;
  onNavigate?: () => void;
}

function SidebarContent({ collapsed, onNavigate }: SidebarContentProps) {
  const { user } = useAuth();

  return (
    <nav className="flex h-full flex-col" aria-label="Principal">
      <div className="flex h-16 shrink-0 items-center border-b border-line">
        {brandMark(collapsed)}
      </div>
      <div className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        {NAV_SECTIONS.map((section) => {
          const items = section.items.filter(
            (item) =>
              !item.permission || userHasPermission(user, item.permission),
          );
          if (items.length === 0) return null;
          return (
            <div key={section.title}>
              {!collapsed && (
                <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-widest text-faint">
                  {section.title}
                </p>
              )}
              <ul className="space-y-1">
                {items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      onClick={onNavigate}
                      title={collapsed ? item.label : undefined}
                      aria-label={item.label}
                      className={({ isActive }) =>
                        `nx-side-link ${isActive ? 'nx-side-link-active' : ''} ${collapsed ? 'justify-center px-3' : ''}`
                      }
                    >
                      <Icon name={item.icon} size={20} className="shrink-0" />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </nav>
  );
}

function resolvePageTitle(pathname: string): string {
  if (pathname === ROUTES.HOME) return 'Inicio';
  for (const section of NAV_SECTIONS) {
    for (const item of section.items) {
      if (item.to === ROUTES.HOME) continue;
      if (pathname === item.to || pathname.startsWith(`${item.to}/`)) {
        return item.label;
      }
    }
  }
  return 'NEXORA';
}

function MainLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const title = useMemo(() => resolvePageTitle(location.pathname), [location.pathname]);
  const userName = user ? (user.first_name || user.username || 'Usuario') : '';
  const initials = useMemo(() => {
    if (!user) return '?';
    const name = user.first_name || user.username || 'Usuario';
    return name.slice(0, 2).toUpperCase();
  }, [user]);

  return (
    <div className="min-h-screen">
      {/* Sidebar escritorio (colapsable) */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 hidden border-r border-line bg-surface transition-[width] duration-300 lg:flex lg:flex-col ${collapsed ? 'w-[84px]' : 'w-64'}`}
      >
        <SidebarContent collapsed={collapsed} />
        <button
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          className="m-3 flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-muted hover:bg-surface-2 hover:text-foreground"
          aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}
        >
          <Icon name="chevrons-left" size={18} className={`transition-transform duration-300 ${collapsed ? 'rotate-180' : ''}`} />
          {!collapsed && <span className="truncate">Colapsar</span>}
        </button>
      </aside>

      {/* Drawer móvil */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 animate-fade-in bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute inset-y-0 left-0 w-72 animate-slide-up bg-surface shadow-xl">
            <SidebarContent collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      {/* Contenido */}
      <div className={`flex min-h-screen flex-col transition-[padding] duration-300 ${collapsed ? 'lg:pl-[84px]' : 'lg:pl-64'}`}>
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-surface/85 px-4 backdrop-blur lg:px-6">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="nx-btn nx-btn-icon nx-btn-ghost text-muted lg:hidden"
            aria-label="Abrir menú"
          >
            <Icon name="menu" size={22} />
          </button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-foreground">{title}</p>
          </div>
          <ThemeToggle />
          {user && (
            <div className="flex items-center gap-2.5">
              <div className="hidden text-right md:block">
                <p className="text-sm font-semibold text-foreground">{userName}</p>
                <p className="text-[11px] text-faint">
                  {user.roles.map((role) => role.display_name).join(' · ')}
                </p>
              </div>
              <span className="flex h-9 w-9 items-center justify-center rounded-full nx-brand-gradient text-xs font-bold text-white shadow">
                {initials}
              </span>
              <button
                type="button"
                onClick={logout}
                title="Cerrar sesión"
                aria-label="Cerrar sesión"
                className="nx-btn nx-btn-icon nx-btn-ghost text-muted"
              >
                <Icon name="logout" size={20} />
              </button>
            </div>
          )}
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>

        <footer className="border-t border-line px-4 py-4 text-center text-xs text-faint">
          NEXORA · Sistema de facturación e inventario con IA
        </footer>
      </div>
    </div>
  );
}

export default MainLayout;