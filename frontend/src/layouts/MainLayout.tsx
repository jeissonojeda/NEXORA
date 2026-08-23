import { Outlet, NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { ROUTES } from '../routes';

const NAV_ITEMS = [
  { to: ROUTES.HOME, label: 'Inicio' },
  { to: ROUTES.CATEGORIES, label: 'Categorías' },
  { to: ROUTES.PRODUCTS, label: 'Productos' },
  { to: ROUTES.INVENTORY, label: 'Inventario' },
];

function MainLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen flex-col bg-gray-100">
      <header className="bg-white shadow">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between py-4">
            <h1 className="text-lg font-bold text-gray-900">
              Sistema de Facturación e Inventario
            </h1>
            {user && (
              <div className="flex items-center gap-3">
                <span className="hidden text-sm text-gray-600 sm:inline">
                  {user.first_name || user.username}
                  {user.roles.length > 0 && (
                    <span className="ml-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                      {user.roles.map((role) => role.display_name).join(', ')}
                    </span>
                  )}
                </span>
                <button
                  type="button"
                  onClick={logout}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Salir
                </button>
              </div>
            )}
          </div>
          <nav className="-mb-px flex gap-4 overflow-x-auto" aria-label="Principal">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === ROUTES.HOME}
                className={({ isActive }) =>
                  `whitespace-nowrap border-b-2 px-1 pb-3 pt-1 text-sm font-medium ${
                    isActive
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
      <footer className="bg-white py-4 text-center text-sm text-gray-500">
        Fase 3 — Productos e Inventario
      </footer>
    </div>
  );
}

export default MainLayout;
