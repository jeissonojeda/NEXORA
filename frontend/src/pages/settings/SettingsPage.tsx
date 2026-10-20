import { useEffect, useMemo, useState } from 'react';
import PageHeader from '../../components/ui/PageHeader';
import LoadingState from '../../components/ui/LoadingState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import { useAsync, extractErrorMessage } from '../../hooks/useAsync';
import { useAuth } from '../../contexts/AuthContext';
import { useSettings } from '../../contexts/SettingsContext';
import { userHasPermission } from '../../utils/permissions';
import {
  getSettings,
  listCurrencies,
  updateSettings,
  listTaxes,
  createTax,
  updateTax,
  deactivateTax,
  uploadLogo,
  deleteLogo,
  fetchLogoBlob,
} from '../../services/settings';
import type { ApiCurrency, ApiTax, ApiSettings } from '../../types/settings';
import Modal from '../../components/ui/Modal';
import { formatCurrency } from '../../utils/format';

const PAPER_WIDTHS = ['58mm', '80mm', 'A5', 'A4'];

export default function SettingsPage() {
  const { user } = useAuth();
  const { reload: reloadGlobalSettings, settings: globalSettings } = useSettings();
  const canWrite = userHasPermission(user, 'settings.update');
  const canReadTaxes = userHasPermission(user, 'settings.read');

  const [activeTab, setActiveTab] = useState<'moneda' | 'impuestos' | 'negocio' | 'impresion'>('moneda');

  const settingsState = useAsync(() => getSettings(), []);
  const currenciesState = useAsync(() => listCurrencies(), []);
  const taxesState = useAsync(() => listTaxes(true), []);

  const settings = settingsState.data ?? globalSettings;

  const [currencyCode, setCurrencyCode] = useState(settings?.currency_code ?? 'COP');
  const [confirmCurrency, setConfirmCurrency] = useState(false);
  const [savingCurrency, setSavingCurrency] = useState(false);
  const [currencyError, setCurrencyError] = useState<string | null>(null);
  const [currencySaved, setCurrencySaved] = useState(false);

  const [taxModalOpen, setTaxModalOpen] = useState(false);
  const [editingTax, setEditingTax] = useState<ApiTax | null>(null);
  const [taxName, setTaxName] = useState('');
  const [taxRate, setTaxRate] = useState('');
  const [taxDefault, setTaxDefault] = useState(false);
  const [taxActive, setTaxActive] = useState(true);
  const [taxBusy, setTaxBusy] = useState(false);
  const [taxError, setTaxError] = useState<string | null>(null);

  const [businessName, setBusinessName] = useState(settings?.business_name ?? 'NEXORA');
  const [businessTaxId, setBusinessTaxId] = useState(settings?.business_tax_id ?? '');
  const [businessAddress, setBusinessAddress] = useState(settings?.business_address ?? '');
  const [businessPhone, setBusinessPhone] = useState(settings?.business_phone ?? '');
  const [businessEmail, setBusinessEmail] = useState(settings?.business_email ?? '');
  const [businessLegalName, setBusinessLegalName] = useState(settings?.business_legal_name ?? '');
  const [businessHeaderText, setBusinessHeaderText] = useState(settings?.business_header_text ?? '');
  const [businessAdditionalInfo, setBusinessAdditionalInfo] = useState(settings?.business_additional_info ?? '');
  const [savingBusiness, setSavingBusiness] = useState(false);
  const [businessMsg, setBusinessMsg] = useState<string | null>(null);

  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [logoBusy, setLogoBusy] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const [printLogoSize, setPrintLogoSize] = useState(settings?.print_logo_size ?? 'medium');
  const [printLogoAlign, setPrintLogoAlign] = useState(settings?.print_logo_align ?? 'left');
  const [printShowCompanyName, setPrintShowCompanyName] = useState(settings?.print_show_company_name ?? true);
  const [printShowNit, setPrintShowNit] = useState(settings?.print_show_nit ?? true);
  const [printShowAddress, setPrintShowAddress] = useState(settings?.print_show_address ?? true);
  const [printShowPhone, setPrintShowPhone] = useState(settings?.print_show_phone ?? true);
  const [printShowEmail, setPrintShowEmail] = useState(settings?.print_show_email ?? true);
  const [printShowHeaderText, setPrintShowHeaderText] = useState(settings?.print_show_header_text ?? true);
  const [printShowAdditionalInfo, setPrintShowAdditionalInfo] = useState(settings?.print_show_additional_info ?? true);
  const [printShowLegalFooter, setPrintShowLegalFooter] = useState(settings?.print_show_legal_footer ?? true);
  const [printShowCustomerInfo, setPrintShowCustomerInfo] = useState(settings?.print_show_customer_info ?? true);
  const [printShowSeller, setPrintShowSeller] = useState(settings?.print_show_seller ?? true);
  const [printShowPaymentMethod, setPrintShowPaymentMethod] = useState(settings?.print_show_payment_method ?? true);
  const [printShowSaleDate, setPrintShowSaleDate] = useState(settings?.print_show_sale_date ?? true);
  const [printShowBarcode, setPrintShowBarcode] = useState(settings?.print_show_barcode ?? false);
  const [printShowUnit, setPrintShowUnit] = useState(settings?.print_show_unit ?? true);
  const [printShowDiscount, setPrintShowDiscount] = useState(settings?.print_show_discount ?? true);
  const [printShowTax, setPrintShowTax] = useState(settings?.print_show_tax ?? true);
  const [printAlignment, setPrintAlignment] = useState(settings?.print_alignment ?? 'left');
  const [printMarginMm, setPrintMarginMm] = useState(String(settings?.print_margin_mm ?? 5));

  const [printerName, setPrinterName] = useState(settings?.printer_name ?? '');
  const [paperWidth, setPaperWidth] = useState(settings?.paper_width ?? '80mm');
  const [printCopies, setPrintCopies] = useState(String(settings?.print_copies ?? 1));
  const [printFont, setPrintFont] = useState(settings?.print_font_size ?? '12px');
  const [printShowLogo, setPrintShowLogo] = useState(settings?.print_show_logo ?? true);
  const [printShowContact, setPrintShowContact] = useState(settings?.print_show_contact ?? true);
  const [printShowTaxId, setPrintShowTaxId] = useState(settings?.print_show_tax_id ?? false);
  const [printFooter, setPrintFooter] = useState(settings?.print_footer_text ?? '¡Gracias por su compra!');
  const [savingPrint, setSavingPrint] = useState(false);
  const [printMsg, setPrintMsg] = useState<string | null>(null);

  useEffect(() => {
    if (settings) {
      setCurrencyCode(settings.currency_code);
      setBusinessName(settings.business_name);
      setBusinessTaxId(settings.business_tax_id ?? '');
      setBusinessAddress(settings.business_address ?? '');
      setBusinessPhone(settings.business_phone ?? '');
      setBusinessEmail(settings.business_email ?? '');
      setBusinessLegalName(settings.business_legal_name ?? '');
      setBusinessHeaderText(settings.business_header_text ?? '');
      setBusinessAdditionalInfo(settings.business_additional_info ?? '');
      setPrinterName(settings.printer_name ?? '');
      setPaperWidth(settings.paper_width);
      setPrintCopies(String(settings.print_copies));
      setPrintFont(settings.print_font_size);
      setPrintShowLogo(settings.print_show_logo);
      setPrintShowContact(settings.print_show_contact);
      setPrintShowTaxId(settings.print_show_tax_id);
      setPrintFooter(settings.print_footer_text ?? '¡Gracias por su compra!');
      setPrintLogoSize(settings.print_logo_size ?? 'medium');
      setPrintLogoAlign(settings.print_logo_align ?? 'left');
      setPrintShowCompanyName(settings.print_show_company_name);
      setPrintShowNit(settings.print_show_nit);
      setPrintShowAddress(settings.print_show_address);
      setPrintShowPhone(settings.print_show_phone);
      setPrintShowEmail(settings.print_show_email);
      setPrintShowHeaderText(settings.print_show_header_text);
      setPrintShowAdditionalInfo(settings.print_show_additional_info);
      setPrintShowLegalFooter(settings.print_show_legal_footer);
      setPrintShowCustomerInfo(settings.print_show_customer_info);
      setPrintShowSeller(settings.print_show_seller);
      setPrintShowPaymentMethod(settings.print_show_payment_method);
      setPrintShowSaleDate(settings.print_show_sale_date);
      setPrintShowBarcode(settings.print_show_barcode);
      setPrintShowUnit(settings.print_show_unit);
      setPrintShowDiscount(settings.print_show_discount);
      setPrintShowTax(settings.print_show_tax);
      setPrintAlignment(settings.print_alignment ?? 'left');
      setPrintMarginMm(String(settings.print_margin_mm ?? 5));
    }
  }, [settings]);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    if (settings?.logo_filename) {
      fetchLogoBlob()
        .then((blob) => {
          if (cancelled) return;
          objectUrl = URL.createObjectURL(blob);
          setLogoUrl(objectUrl);
        })
        .catch(() => {
          if (!cancelled) setLogoUrl(null);
        });
    } else {
      setLogoUrl(null);
    }
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [settings?.logo_filename]);

  const currencyPreview = useMemo(() => {
    // Refleja la moneda seleccionada (no la guardada) usando el catálogo.
    const selected = (currenciesState.data ?? []).find(
      (c) => c.code === currencyCode,
    );
    const locale = selected?.locale ?? settings?.currency_locale ?? 'es-CO';
    const decimals = selected?.decimals ?? settings?.decimal_places ?? 2;
    try {
      return 1234.56.toLocaleString(locale, {
        style: 'currency',
        currency: currencyCode,
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    } catch {
      return formatCurrency(1234.56);
    }
  }, [settings, currencyCode, currenciesState.data]);

  async function saveCurrency(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite) return;
    setSavingCurrency(true);
    setCurrencyError(null);
    setCurrencySaved(false);
    try {
      const res = await updateSettings({
        currency_code: currencyCode,
        confirm_currency_change: confirmCurrency,
      });
      applyToContext(res);
      setCurrencySaved(true);
      setConfirmCurrency(false);
      void reloadGlobalSettings();
      void settingsState.reload();
    } catch (err) {
      setCurrencyError(extractErrorMessage(err));
    } finally {
      setSavingCurrency(false);
    }
  }

  function applyToContext(_s: ApiSettings) {
    void reloadGlobalSettings();
  }

  function openNewTax() {
    setEditingTax(null);
    setTaxName('');
    setTaxRate('');
    setTaxDefault(false);
    setTaxActive(true);
    setTaxError(null);
    setTaxModalOpen(true);
  }

  function openEditTax(t: ApiTax) {
    setEditingTax(t);
    setTaxName(t.name);
    setTaxRate(String(t.rate));
    setTaxDefault(t.is_default);
    setTaxActive(t.is_active);
    setTaxError(null);
    setTaxModalOpen(true);
  }

  async function saveTax(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite) return;
    setTaxBusy(true);
    setTaxError(null);
    try {
      if (editingTax) {
        await updateTax(editingTax.id, {
          name: taxName,
          rate: taxRate,
          is_active: taxActive,
          is_default: taxDefault,
        });
      } else {
        await createTax({
          name: taxName,
          rate: taxRate,
          description: '',
          is_active: taxActive,
          is_default: taxDefault,
        });
      }
      setTaxModalOpen(false);
      void taxesState.reload();
    } catch (err) {
      setTaxError(extractErrorMessage(err));
    } finally {
      setTaxBusy(false);
    }
  }

  async function toggleDeactivate(t: ApiTax) {
    if (!canWrite) return;
    try {
      await deactivateTax(t.id);
      void taxesState.reload();
    } catch (err) {
      alert(extractErrorMessage(err));
    }
  }

  async function saveBusiness(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite) return;
    setSavingBusiness(true);
    setBusinessMsg(null);
    try {
      const res = await updateSettings({
        business_name: businessName,
        business_tax_id: businessTaxId || null,
        business_address: businessAddress || null,
        business_phone: businessPhone || null,
        business_email: businessEmail || null,
        business_legal_name: businessLegalName || null,
        business_header_text: businessHeaderText || null,
        business_additional_info: businessAdditionalInfo || null,
      });
      applyToContext(res);
      setBusinessMsg('Datos guardados');
      void settingsState.reload();
      void reloadGlobalSettings();
    } catch (err) {
      setBusinessMsg(extractErrorMessage(err));
    } finally {
      setSavingBusiness(false);
    }
  }

  async function savePrint(e: React.FormEvent) {
    e.preventDefault();
    if (!canWrite) return;
    setSavingPrint(true);
    setPrintMsg(null);
    try {
      const res = await updateSettings({
        printer_name: printerName || null,
        paper_width: paperWidth,
        print_copies: Number(printCopies) || 1,
        print_font_size: printFont,
        print_show_logo: printShowLogo,
        print_show_contact: printShowContact,
        print_show_tax_id: printShowTaxId,
        print_footer_text: printFooter || null,
        print_logo_size: printLogoSize,
        print_logo_align: printLogoAlign,
        print_show_company_name: printShowCompanyName,
        print_show_nit: printShowNit,
        print_show_address: printShowAddress,
        print_show_phone: printShowPhone,
        print_show_email: printShowEmail,
        print_show_header_text: printShowHeaderText,
        print_show_additional_info: printShowAdditionalInfo,
        print_show_legal_footer: printShowLegalFooter,
        print_show_customer_info: printShowCustomerInfo,
        print_show_seller: printShowSeller,
        print_show_payment_method: printShowPaymentMethod,
        print_show_sale_date: printShowSaleDate,
        print_show_barcode: printShowBarcode,
        print_show_unit: printShowUnit,
        print_show_discount: printShowDiscount,
        print_show_tax: printShowTax,
        print_alignment: printAlignment,
        print_margin_mm: Number(printMarginMm) || 0,
      });
      applyToContext(res);
      setPrintMsg('Configuración guardada');
      void settingsState.reload();
    } catch (err) {
      setPrintMsg(extractErrorMessage(err));
    } finally {
      setSavingPrint(false);
    }
  }

  async function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !canWrite) return;
    setLogoError(null);
    if (file.size > 1024 * 1024) {
      setLogoError('El logotipo supera el límite de 1 MB');
      return;
    }
    setLogoBusy(true);
    try {
      const res = await uploadLogo(file);
      applyToContext(res);
      void settingsState.reload();
    } catch (err) {
      setLogoError(extractErrorMessage(err));
    } finally {
      setLogoBusy(false);
      e.target.value = '';
    }
  }

  async function handleLogoDelete() {
    if (!canWrite) return;
    setLogoError(null);
    setLogoBusy(true);
    try {
      const res = await deleteLogo();
      applyToContext(res);
      void settingsState.reload();
    } catch (err) {
      setLogoError(extractErrorMessage(err));
    } finally {
      setLogoBusy(false);
    }
  }

  const loading = settingsState.loading || currenciesState.loading;
  const err = settingsState.error || currenciesState.error;

  return (
    <div className="animate-fade-in space-y-6">
      <PageHeader title="Configuración" subtitle="Moneda, impuestos, datos del negocio e impresión" />
      {loading && <LoadingState rows={4} />}
      {err && <ErrorAlert message={extractErrorMessage(err)} />}
      {!loading && (
        <>
          <div className="flex flex-wrap gap-2 text-sm">
            {(
              [
                ['moneda', 'Moneda'],
                ['impuestos', 'Impuestos'],
                ['negocio', 'Negocio'],
                ['impresion', 'Impresión'],
              ] as const
            ).map(([k, l]) => (
              <button
                key={k}
                className={`nx-chip ${activeTab === k ? 'bg-primary/15 text-primary' : ''}`}
                onClick={() => setActiveTab(k)}
              >
                {l}
              </button>
            ))}
          </div>

          {activeTab === 'moneda' && (
            <div className="max-w-2xl space-y-6">
              <form className="space-y-4 rounded-xl border border-line bg-surface p-4 shadow-soft" onSubmit={saveCurrency}>
                <div>
                  <label className="nx-label">Moneda</label>
                  <select
                    className="nx-select"
                    value={currencyCode}
                    onChange={(e) => setCurrencyCode(e.target.value)}
                    disabled={!canWrite}
                  >
                    {(currenciesState.data ?? []).map((c: ApiCurrency) => (
                      <option key={c.code} value={c.code}>
                        {c.code} — {c.name} ({c.symbol})
                      </option>
                    ))}
                  </select>
                </div>
                {currencyCode !== (settings?.currency_code ?? 'COP') && (
                  <label className="flex items-center gap-2 text-sm text-muted">
                    <input
                      type="checkbox"
                      checked={confirmCurrency}
                      onChange={(e) => setConfirmCurrency(e.target.checked)}
                      disabled={!canWrite}
                    />
                    Confirmo el cambio de moneda (puede requerirse si hay ventas/compras)
                  </label>
                )}
                <button type="submit" className="nx-btn nx-btn-primary" disabled={savingCurrency || !canWrite}>
                  {savingCurrency ? 'Guardando…' : 'Guardar'}
                </button>
                {currencyError && <ErrorAlert message={currencyError} />}
                {currencySaved && <p className="text-sm text-green-600 dark:text-green-400">Moneda actualizada</p>}
                <div className="text-sm text-muted">Vista previa: {currencyPreview}</div>
              </form>
            </div>
          )}

          {activeTab === 'impuestos' && canReadTaxes && (
            <div className="space-y-4">
              <div className="flex justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">Impuestos</h2>
                  <p className="text-sm text-muted">Configura los impuestos aplicables</p>
                </div>
                <button className="nx-btn nx-btn-primary" onClick={openNewTax} disabled={!canWrite}>
                  Nuevo impuesto
                </button>
              </div>
              <div className="overflow-x-auto rounded-xl border border-line bg-surface">
                <table className="min-w-full divide-y divide-line text-sm">
                  <thead className="bg-surface-2">
                    <tr>
                      <th className="px-4 py-2 text-left font-semibold text-muted">Nombre</th>
                      <th className="px-4 py-2 text-left font-semibold text-muted">Tasa %</th>
                      <th className="px-4 py-2 text-left font-semibold text-muted">Predeterminado</th>
                      <th className="px-4 py-2 text-left font-semibold text-muted">Activo</th>
                      <th className="px-4 py-2 text-right font-semibold text-muted">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {(taxesState.data ?? []).map((t: ApiTax) => (
                      <tr key={t.id}>
                        <td className="px-4 py-2">{t.name}</td>
                        <td className="px-4 py-2">{t.rate}%</td>
                        <td className="px-4 py-2">{t.is_default ? 'Sí' : 'No'}</td>
                        <td className="px-4 py-2">{t.is_active ? 'Sí' : 'No'}</td>
                        <td className="px-4 py-2 text-right">
                          <button className="nx-btn nx-btn-ghost nx-btn-sm" onClick={() => openEditTax(t)} disabled={!canWrite}>Editar</button>
                          {t.is_active && (
                            <button className="nx-btn nx-btn-ghost nx-btn-sm text-red-500" onClick={() => toggleDeactivate(t)} disabled={!canWrite}>Desactivar</button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'negocio' && (
            <form className="max-w-2xl space-y-4 rounded-xl border border-line bg-surface p-4 shadow-soft" onSubmit={saveBusiness}>
              <div>
                <label className="nx-label">Nombre del negocio</label>
                <input className="nx-input" value={businessName} onChange={(e) => setBusinessName(e.target.value)} disabled={!canWrite} />
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className="nx-label">NIT/Identificación tributaria</label>
                  <input className="nx-input" value={businessTaxId} onChange={(e) => setBusinessTaxId(e.target.value)} disabled={!canWrite} />
                </div>
                <div>
                  <label className="nx-label">Teléfono</label>
                  <input className="nx-input" value={businessPhone} onChange={(e) => setBusinessPhone(e.target.value)} disabled={!canWrite} />
                </div>
              </div>
              <div>
                <label className="nx-label">Dirección</label>
                <input className="nx-input" value={businessAddress} onChange={(e) => setBusinessAddress(e.target.value)} disabled={!canWrite} />
              </div>
              <div>
                <label className="nx-label">Correo electrónico</label>
                <input className="nx-input" type="email" value={businessEmail} onChange={(e) => setBusinessEmail(e.target.value)} disabled={!canWrite} />
              </div>
              <div>
                <label className="nx-label">Razón social (opcional)</label>
                <input className="nx-input" value={businessLegalName} onChange={(e) => setBusinessLegalName(e.target.value)} disabled={!canWrite} />
              </div>
              <div>
                <label className="nx-label">Texto de encabezado (opcional)</label>
                <input className="nx-input" value={businessHeaderText} onChange={(e) => setBusinessHeaderText(e.target.value)} disabled={!canWrite} />
              </div>
              <div>
                <label className="nx-label">Información adicional (opcional)</label>
                <textarea className="nx-input" rows={2} value={businessAdditionalInfo} onChange={(e) => setBusinessAdditionalInfo(e.target.value)} disabled={!canWrite} />
              </div>

              <div className="space-y-2 rounded-lg border border-line p-3">
                <label className="nx-label">Logotipo</label>
                <div className="flex items-center gap-3">
                  {logoUrl ? (
                    <img src={logoUrl} alt="Logotipo" className="h-16 w-16 rounded object-contain" />
                  ) : (
                    <div className="flex h-16 w-16 items-center justify-center rounded bg-surface-2 text-xs text-faint">
                      Sin logo
                    </div>
                  )}
                  <div className="flex gap-2">
                    <label className={`nx-btn nx-btn-secondary ${!canWrite || logoBusy ? 'pointer-events-none opacity-50' : 'cursor-pointer'}`}>
                      {logoBusy ? 'Subiendo…' : 'Subir logo'}
                      <input
                        type="file"
                        accept="image/png,image/jpeg"
                        className="hidden"
                        onChange={handleLogoChange}
                        disabled={!canWrite || logoBusy}
                      />
                    </label>
                    {logoUrl && (
                      <button type="button" className="nx-btn nx-btn-ghost text-red-500" onClick={handleLogoDelete} disabled={!canWrite || logoBusy}>
                        Eliminar
                      </button>
                    )}
                  </div>
                </div>
                <p className="text-xs text-faint">PNG o JPEG, máximo 1 MB.</p>
                {logoError && <ErrorAlert message={logoError} />}
              </div>

              <button type="submit" className="nx-btn nx-btn-primary" disabled={savingBusiness || !canWrite}>
                {savingBusiness ? 'Guardando…' : 'Guardar'}
              </button>
              {businessMsg && <p className="text-sm text-faint">{businessMsg}</p>}
            </form>
          )}

          {activeTab === 'impresion' && (
            <form className="max-w-2xl space-y-4 rounded-xl border border-line bg-surface p-4 shadow-soft" onSubmit={savePrint}>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className="nx-label">Impresora (nombre opcional)</label>
                  <input className="nx-input" value={printerName} onChange={(e) => setPrinterName(e.target.value)} disabled={!canWrite} />
                </div>
                <div>
                  <label className="nx-label">Ancho de papel</label>
                  <select className="nx-select" value={paperWidth} onChange={(e) => setPaperWidth(e.target.value)} disabled={!canWrite}>
                    {PAPER_WIDTHS.map((w) => (
                      <option key={w} value={w}>{w}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="nx-label">Copias</label>
                  <input className="nx-input" type="number" min="1" value={printCopies} onChange={(e) => setPrintCopies(e.target.value)} disabled={!canWrite} />
                </div>
                <div>
                  <label className="nx-label">Tamaño de fuente</label>
                  <input className="nx-input" value={printFont} onChange={(e) => setPrintFont(e.target.value)} disabled={!canWrite} />
                </div>
                <div>
                  <label className="nx-label">Márgenes (mm)</label>
                  <input className="nx-input" type="number" min="0" max="30" value={printMarginMm} onChange={(e) => setPrintMarginMm(e.target.value)} disabled={!canWrite} />
                </div>
                <div>
                  <label className="nx-label">Alineación del texto</label>
                  <select className="nx-select" value={printAlignment} onChange={(e) => setPrintAlignment(e.target.value)} disabled={!canWrite}>
                    <option value="left">Izquierda</option>
                    <option value="center">Centro</option>
                    <option value="right">Derecha</option>
                  </select>
                </div>
                <div>
                  <label className="nx-label">Tamaño del logo</label>
                  <select className="nx-select" value={printLogoSize} onChange={(e) => setPrintLogoSize(e.target.value)} disabled={!canWrite}>
                    <option value="small">Pequeño</option>
                    <option value="medium">Medio</option>
                    <option value="large">Grande</option>
                  </select>
                </div>
                <div>
                  <label className="nx-label">Alineación del logo</label>
                  <select className="nx-select" value={printLogoAlign} onChange={(e) => setPrintLogoAlign(e.target.value)} disabled={!canWrite}>
                    <option value="left">Izquierda</option>
                    <option value="center">Centro</option>
                    <option value="right">Derecha</option>
                  </select>
                </div>
              </div>
              <fieldset className="space-y-2 text-sm">
                <legend className="nx-label">Elementos visibles en el comprobante</legend>
                <div className="grid grid-cols-2 gap-2">
                  {([
                    ['Logotipo', printShowLogo, setPrintShowLogo],
                    ['Nombre del negocio', printShowCompanyName, setPrintShowCompanyName],
                    ['NIT/ID tributario', printShowNit, setPrintShowNit],
                    ['Dirección', printShowAddress, setPrintShowAddress],
                    ['Teléfono', printShowPhone, setPrintShowPhone],
                    ['Correo', printShowEmail, setPrintShowEmail],
                    ['Datos de contacto', printShowContact, setPrintShowContact],
                    ['Encabezado', printShowHeaderText, setPrintShowHeaderText],
                    ['Información adicional', printShowAdditionalInfo, setPrintShowAdditionalInfo],
                    ['Pie legal', printShowLegalFooter, setPrintShowLegalFooter],
                    ['Datos del cliente', printShowCustomerInfo, setPrintShowCustomerInfo],
                    ['Vendedor', printShowSeller, setPrintShowSeller],
                    ['Método de pago', printShowPaymentMethod, setPrintShowPaymentMethod],
                    ['Fecha de venta', printShowSaleDate, setPrintShowSaleDate],
                    ['Código de barras', printShowBarcode, setPrintShowBarcode],
                    ['Unidad', printShowUnit, setPrintShowUnit],
                    ['Descuento', printShowDiscount, setPrintShowDiscount],
                    ['Impuesto', printShowTax, setPrintShowTax],
                  ] as const).map(([label, value, setter]) => (
                    <label key={label} className="flex items-center gap-2">
                      <input type="checkbox" checked={value} onChange={(e) => setter(e.target.checked)} disabled={!canWrite} />
                      {label}
                    </label>
                  ))}
                </div>
              </fieldset>
              <div>
                <label className="nx-label">Pie de página</label>
                <input className="nx-input" value={printFooter} onChange={(e) => setPrintFooter(e.target.value)} disabled={!canWrite} />
              </div>
              <button type="submit" className="nx-btn nx-btn-primary" disabled={savingPrint || !canWrite}>
                {savingPrint ? 'Guardando…' : 'Guardar'}
              </button>
              {printMsg && <p className="text-sm text-faint">{printMsg}</p>}
            </form>
          )}
        </>
      )}

      <Modal open={taxModalOpen} onClose={() => setTaxModalOpen(false)} title={editingTax ? 'Editar impuesto' : 'Nuevo impuesto'}>
        <form className="space-y-4" onSubmit={saveTax}>
          <div>
            <label className="nx-label">Nombre</label>
            <input className="nx-input" value={taxName} onChange={(e) => setTaxName(e.target.value)} required />
          </div>
          <div>
            <label className="nx-label">Tasa (%)</label>
            <input className="nx-input" type="number" step="0.01" min="0" max="100" value={taxRate} onChange={(e) => setTaxRate(e.target.value)} required />
          </div>
          <div className="space-y-2 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={taxDefault} onChange={(e) => setTaxDefault(e.target.checked)} />
              Predeterminado
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={taxActive} onChange={(e) => setTaxActive(e.target.checked)} />
              Activo
            </label>
          </div>
          {taxError && <ErrorAlert message={taxError} />}
          <div className="flex justify-end gap-2">
            <button type="button" className="nx-btn nx-btn-secondary" onClick={() => setTaxModalOpen(false)} disabled={taxBusy}>Cancelar</button>
            <button type="submit" className="nx-btn nx-btn-primary" disabled={taxBusy}>{taxBusy ? 'Guardando…' : 'Guardar'}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}