import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import { useAuth } from './contexts/AuthContext';
import { ROUTES } from './routes';
import HomePage from './pages/home/HomePage';
import LoginPage from './pages/auth/LoginPage';
import CategoriesPage from './pages/categories/CategoriesPage';
import ProductsPage from './pages/products/ProductsPage';
import SuppliersPage from './pages/suppliers/SuppliersPage';
import InventoryPage from './pages/inventory/InventoryPage';
import PurchasesPage from './pages/purchases/PurchasesPage';
import PurchaseDetailPage from './pages/purchases/PurchaseDetailPage';
import CustomersPage from './pages/customers/CustomersPage';
import CustomerDetailPage from './pages/customers/CustomerDetailPage';
import SalesPage from './pages/sales/SalesPage';
import PointOfSalePage from './pages/sales/PointOfSalePage';
import SaleDetailPage from './pages/sales/SaleDetailPage';
import CashPage from './pages/cash/CashPage';
import ReportsPage from './pages/reports/ReportsPage';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, initializing } = useAuth();
  const location = useLocation();

  if (initializing) {
    return (
      <p className="py-20 text-center text-sm text-gray-500">
        Verificando sesión…
      </p>
    );
  }
  if (!user) {
    return <Navigate to={ROUTES.LOGIN} state={{ from: location.pathname }} replace />;
  }
  return children;
}

function App() {
  return (
    <Routes>
      <Route path={ROUTES.LOGIN} element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <MainLayout />
          </RequireAuth>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="categorias" element={<CategoriesPage />} />
        <Route path="proveedores" element={<SuppliersPage />} />
        <Route path="productos" element={<ProductsPage />} />
        <Route path="inventario" element={<InventoryPage />} />
        <Route path="purchases" element={<PurchasesPage />} />
        <Route path="purchases/:id" element={<PurchaseDetailPage />} />
        <Route path={ROUTES.CUSTOMERS} element={<CustomersPage />} />
        <Route path={`${ROUTES.CUSTOMERS}/:id`} element={<CustomerDetailPage />} />
        <Route path="ventas" element={<SalesPage />} />
        <Route path="ventas/:id" element={<SaleDetailPage />} />
            <Route path="pos" element={<PointOfSalePage />} />
            <Route path={ROUTES.CASH} element={<CashPage />} />
            <Route path={ROUTES.REPORTS} element={<ReportsPage />} />
      </Route>
      <Route path="*" element={<Navigate to={ROUTES.HOME} replace />} />
    </Routes>
  );
}

export default App;
