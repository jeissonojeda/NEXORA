import { useTheme } from '../../contexts/ThemeContext';
import Icon from './Icon';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const dark = theme === 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={dark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
      title={dark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
      className="nx-btn nx-btn-icon nx-btn-ghost text-muted"
    >
      <Icon name={dark ? 'sun' : 'moon'} size={20} />
    </button>
  );
}