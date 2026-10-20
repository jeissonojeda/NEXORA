import PageHeader from '../../components/ui/PageHeader';
import CategoriesManager from '../../components/domain/CategoriesManager';

export default function CategoriesPage() {
  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        title="Categorías"
        subtitle="Organiza tus productos por categorías."
      />
      <CategoriesManager />
    </div>
  );
}
