import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import { useAuth } from './contexts/AuthContext';
import { useLicense } from './contexts/LicenseContext';
import { ROUTES } from './routes';
import ErrorBoundary from './components/ui/ErrorBoundary';
import PageLoader from './components/ui/PageLoader';
import ActivationPage from './pages/license/ActivationPage';
import HomePage from './pages/home/HomePage';
import LoginPage from './pages/auth/LoginPage';
import CategoriesPage from './pages/categories/CategoriesPage';
import ProductsPage from './pages/products/ProductsPage';
import InventoryPage from './pages/inventory/InventoryPage';
import ComprasProveedoresPage from './pages/purchases/ComprasProveedoresPage';
import PurchaseDetailPage from './pages/purchases/PurchaseDetailPage';
import CustomersPage from './pages/customers/CustomersPage';
import CustomerDetailPage from './pages/customers/CustomerDetailPage';
import ReceivablesPage from './pages/customers/ReceivablesPage';
import SalesPage from './pages/sales/SalesPage';
import PointOfSalePage from './pages/sales/PointOfSalePage';
import SaleDetailPage from './pages/sales/SaleDetailPage';
import CashPage from './pages/cash/CashPage';
import ReportsPage from './pages/reports/ReportsPage';
import AIPage from './pages/ai/AIPage';
import SettingsPage from './pages/settings/SettingsPage';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, initializing } = useAuth();
  const location = useLocation();

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--nx-bg)]">
        <div className="w-full max-w-sm px-4">
          <PageLoader message="Verificando sesión…" />
        </div>
      </div>
    );
  }
  if (!user) {
    return <Navigate to={ROUTES.LOGIN} state={{ from: location.pathname }} replace />;
  }
  return children;
}

function LicenseGate({ children }: { children: React.ReactNode }) {
  const { status, loading } = useLicense();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--nx-bg)]">
        <div className="w-full max-w-sm px-4">
          <PageLoader message="Verificando licencia…" />
        </div>
      </div>
    );
  }
  if (status && status.enforced && !status.activated) {
    return <ActivationPage />;
  }
  return children;
}

function RoutedErrorBoundary({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <ErrorBoundary
      // La key reinicia el boundary al cambiar de ruta: un error en una
      // página no arrastra el fallo a las demás.
      key={location.pathname}
      context="route"
      title="Se produjo un error al mostrar esta pantalla."
      description="El módulo no pudo renderizarse, pero el resto de NEXORA sigue disponible. Puedes volver al inicio o recargar."
      retryLabel="Recargar"
      onRetry={() => window.location.reload()}
      secondaryLabel="Volver al inicio"
      onSecondary={() => navigate(ROUTES.HOME)}
    >
      {children}
    </ErrorBoundary>
  );
}

function App() {
  return (
    <RoutedErrorBoundary>
    <Routes>
      <Route path={ROUTES.LICENSE} element={<ActivationPage />} />
      <Route path={ROUTES.LOGIN} element={<LoginPage />} />
      <Route
        path="/"
        element={
          <LicenseGate>
            <RequireAuth>
              <MainLayout />
            </RequireAuth>
          </LicenseGate>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="categorias" element={<CategoriesPage />} />
        <Route path="productos" element={<ProductsPage />} />
        <Route path="inventario" element={<InventoryPage />} />
        <Route path="compras-proveedores" element={<ComprasProveedoresPage />} />
        <Route
          path="proveedores"
          element={<ComprasProveedoresPage initialTab="proveedores" />}
        />
        <Route path="purchases" element={<ComprasProveedoresPage />} />
        <Route path="purchases/:id" element={<PurchaseDetailPage />} />
        <Route path={ROUTES.CUSTOMERS} element={<CustomersPage />} />
        <Route path={`${ROUTES.CUSTOMERS}/:id`} element={<CustomerDetailPage />} />
        <Route path={ROUTES.RECEIVABLES} element={<ReceivablesPage />} />
        <Route path="ventas" element={<SalesPage />} />
        <Route path="ventas/:id" element={<SaleDetailPage />} />
        <Route path="pos" element={<PointOfSalePage />} />
        <Route path={ROUTES.CASH} element={<CashPage />} />
        <Route path={ROUTES.REPORTS} element={<ReportsPage />} />
        <Route path={ROUTES.AI} element={<AIPage />} />
        <Route path={ROUTES.SETTINGS} element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to={ROUTES.HOME} replace />} />
    </Routes>
    </RoutedErrorBoundary>
  );
}

export default App;