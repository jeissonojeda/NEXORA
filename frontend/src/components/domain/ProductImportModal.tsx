import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage } from '../../hooks/useAsync';
import {
  confirmImport,
  downloadImportErrors,
  downloadImportTemplate,
  listImportBatches,
  listImportEntities,
  previewImport,
} from '../../services/productImport';
import type {
  ImportBatchListResponse,
  ImportConfirmResponse,
  ImportEntitiesResponse,
  ImportEntitySummary,
  ImportPreviewResponse,
  ImportRow,
  ImportRowOverride,
} from '../../types/productImport';
import { userHasPermission } from '../../utils/permissions';
import { formatDateTime } from '../../utils/format';
import Badge from '../ui/Badge';
import LoadingState from '../ui/LoadingState';
import Modal from '../ui/Modal';
import Icon from '../ui/Icon';

type Phase = 'select' | 'preview' | 'processing' | 'result' | 'history';

type OverrideDraft = {
  category?: string;
  supplier?: string;
  tax?: string;
};

const ROW_TONE: Record<ImportRow['status'], 'gray' | 'amber' | 'red'> = {
  VALID: 'gray',
  WARNING: 'amber',
  ERROR: 'red',
};

const ROW_LABEL: Record<ImportRow['status'], string> = {
  VALID: 'Válida',
  WARNING: 'Advertencia',
  ERROR: 'Error',
};

function triggerDownload(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Límite alineado con el backend (MAX_FILE_BYTES = 5 MB). */
const MAX_FILE_BYTES = 5 * 1024 * 1024;
const ALLOWED_EXTENSIONS = ['.xlsx', '.xlsm', '.csv'];

/**
 * Valida el archivo antes de subirlo y devuelve un mensaje claro, o null si
 * es aceptable. Evita enviar al backend archivos inválidos.
 */
function validateFile(file: File): string | null {
  const name = file.name.toLowerCase();
  const hasAllowedExtension = ALLOWED_EXTENSIONS.some((ext) =>
    name.endsWith(ext),
  );
  if (!hasAllowedExtension) {
    return (
      'Formato de archivo no permitido. Usa un archivo Excel (.xlsx) o CSV ' +
      'descargado desde la plantilla.'
    );
  }
  if (file.size === 0) {
    return 'El archivo está vacío. Descarga la plantilla y complétala con tus productos.';
  }
  if (file.size > MAX_FILE_BYTES) {
    return (
      'El archivo supera el límite de 5 MB. Divídelo en varios archivos más ' +
      'pequeños e inténtalo de nuevo.'
    );
  }
  return null;
}

function toOverrideList(
  overrides: Record<number, OverrideDraft>,
): ImportRowOverride[] {
  return Object.entries(overrides)
    .map(([rowNumber, draft]) => ({
      row_number: Number(rowNumber),
      ...draft,
    }))
    .filter(
      (o) => o.category != null || o.supplier != null || o.tax != null,
    )
    .sort((a, b) => a.row_number - b.row_number);
}

const EMPTY_ROW_DATA: ImportRow['data'] = {
  name: '',
  barcode: null,
  description: null,
  unit: null,
  category_name: null,
  category_id: null,
  category_declared: false,
  supplier_name: null,
  supplier_id: null,
  supplier_declared: false,
  tax_name: null,
  tax_id: null,
  purchase_price: null,
  profit_percent: null,
  sale_price: null,
  stock_initial: null,
  minimum_stock: null,
  is_active: null,
  suggested_category: null,
  suggested_supplier: null,
  suggested_tax: null,
};

/**
 * Normaliza una fila del backend rellenando campos ausentes.
 *
 * El objetivo es que una respuesta parcial (backend antiguo, versión en
 * caché o error de esquema) NUNCA provoque `undefined.map`/`undefined.length`
 * ni una pantalla negra durante el render.
 */
function normalizeRow(row: Partial<ImportRow>, index: number): ImportRow {
  const status: ImportRow['status'] =
    row.status === 'VALID' || row.status === 'WARNING' || row.status === 'ERROR'
      ? row.status
      : 'ERROR';
  return {
    row_number: typeof row.row_number === 'number' ? row.row_number : index + 1,
    status,
    messages: Array.isArray(row.messages) ? row.messages : [],
    errors: Array.isArray(row.errors) ? row.errors : [],
    duplicate_of: row.duplicate_of ?? null,
    existing_product_id: row.existing_product_id ?? null,
    data: { ...EMPTY_ROW_DATA, ...(row.data ?? {}) },
  };
}

/**
 * Normaliza la respuesta completa de la previsualización con valores seguros.
 */
function normalizePreview(
  raw: Partial<ImportPreviewResponse>,
  fallbackFileName: string,
): ImportPreviewResponse {
  const rows = Array.isArray(raw.rows)
    ? raw.rows.map((row, index) => normalizeRow(row ?? {}, index))
    : [];
  const entities: Partial<ImportPreviewResponse['entities']> =
    raw.entities ?? {};
  const safeSummary = (summary: Partial<ImportEntitySummary> | undefined) => ({
    existing: summary?.existing ?? 0,
    new: summary?.new ?? 0,
    total: summary?.total ?? 0,
    items: Array.isArray(summary?.items) ? summary.items : [],
  });
  return {
    file_name: raw.file_name ?? fallbackFileName,
    total_rows: raw.total_rows ?? rows.length,
    valid: raw.valid ?? 0,
    warnings: raw.warnings ?? 0,
    errors: raw.errors ?? 0,
    rows,
    entities: {
      suppliers: safeSummary(entities.suppliers),
      categories: safeSummary(entities.categories),
      taxes: safeSummary(entities.taxes),
    },
    declaration_errors: Array.isArray(raw.declaration_errors)
      ? raw.declaration_errors
      : [],
  };
}

function unresolvedFields(row: ImportRow) {
  const data = row.data ?? {};
  return {
    category:
      Boolean(data.category_name) &&
      !data.category_id &&
      !data.category_declared,
    supplier:
      Boolean(data.supplier_name) &&
      !data.supplier_id &&
      !data.supplier_declared,
    tax: Boolean(data.tax_name) && !data.tax_id,
  };
}

type EntityKind = 'suppliers' | 'categories' | 'taxes';

const ENTITY_LABEL: Record<EntityKind, string> = {
  suppliers: 'Proveedores',
  categories: 'Categorías',
  taxes: 'Impuestos',
};

function EntitySummaryPanel({ preview }: { preview: ImportPreviewResponse }) {
  const kinds: EntityKind[] = ['suppliers', 'categories', 'taxes'];
  const hasAny = kinds.some((kind) => preview.entities[kind].total > 0);
  if (!hasAny) return null;

  return (
    <div className="rounded border border-line bg-surface-2/50 p-3">
      <p className="mb-2 text-xs font-semibold">
        Entidades declaradas en el archivo
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        {kinds.map((kind) => {
          const summary = preview.entities[kind];
          if (summary.total === 0) return null;
          return (
            <div key={kind} className="space-y-1">
              <div className="flex items-center gap-2 text-xs font-medium">
                <span>{ENTITY_LABEL[kind]}</span>
                <Badge tone="gray">
                  {summary.existing} existente(s) / {summary.new} nueva(s)
                </Badge>
              </div>
              <ul className="space-y-0.5 text-[11px]">
                {summary.items.map((item) => (
                  <li key={item.name} className="flex items-center gap-1">
                    <span className="text-muted">{item.name}</span>
                    {item.status === 'EXISTING' && (
                      <span className="text-success">· ya existe</span>
                    )}
                    {item.status === 'NEW' && item.can_create && (
                      <span className="text-primary">· se creará</span>
                    )}
                    {item.status === 'NEW' && !item.can_create && (
                      <span className="text-danger">
                        · sin permiso para crearla
                      </span>
                    )}
                    {item.status === 'MISSING' && (
                      <span className="text-danger">
                        · no existe (debes usar uno existente)
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
      {preview.entities.taxes.new > 0 && (
        <p className="mt-2 text-[11px] text-danger">
          Los impuestos no se crean automáticamente. Corrige las filas cuyo
          impuesto no existe antes de confirmar.
        </p>
      )}
    </div>
  );
}

export default function ProductImportModal({ onClose }: { onClose: () => void }) {
  const { user } = useAuth();
  const canImport = userHasPermission(user, 'products.import');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const submitRef = useRef(false);

  const [phase, setPhase] = useState<Phase>('select');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [result, setResult] = useState<ImportConfirmResponse | null>(null);
  const [batches, setBatches] = useState<ImportBatchListResponse | null>(null);
  const [entities, setEntities] = useState<ImportEntitiesResponse | null>(null);
  const [entitiesError, setEntitiesError] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<number, OverrideDraft>>({});
  const [policy, setPolicy] = useState<'SKIP_NEW' | 'UPDATE_EXISTING'>('SKIP_NEW');
  const [onlyIssues, setOnlyIssues] = useState(false);
  const [bulk, setBulk] = useState<OverrideDraft>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canImport) return;
    let active = true;
    listImportEntities()
      .then((res) => {
        if (active) {
          setEntities({
            categories: Array.isArray(res?.categories) ? res.categories : [],
            suppliers: Array.isArray(res?.suppliers) ? res.suppliers : [],
            taxes: Array.isArray(res?.taxes) ? res.taxes : [],
          });
        }
      })
      .catch((err) => {
        if (active) {
          setEntitiesError(extractErrorMessage(err));
        }
      });
    return () => {
      active = false;
    };
  }, [canImport]);

  if (!canImport) {
    return null;
  }

  const overrideList = toOverrideList(overrides);
  const importableCount =
    preview?.rows.filter((r) => r.status !== 'ERROR').length ?? 0;
  const visibleRows =
    preview?.rows.filter((r) => !onlyIssues || r.status !== 'VALID') ?? [];

  async function handleDownloadTemplate() {
    setBusy(true);
    setError(null);
    try {
      const blob = await downloadImportTemplate();
      triggerDownload(blob, 'plantilla_importacion_productos.xlsx');
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function runPreview(
    selected: File,
    override?: ImportRowOverride[],
  ): Promise<boolean> {
    setBusy(true);
    setError(null);
    setPhase('processing');
    try {
      const raw = await previewImport(selected, override);
      // Normaliza la respuesta: tolera campos ausentes sin romper el render.
      setPreview(normalizePreview(raw, selected.name));
      setPhase('preview');
      return true;
    } catch (err) {
      setError(extractErrorMessage(err));
      setPhase('select');
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function handleFileSelected(selected: File | null) {
    setFile(selected);
    setPreview(null);
    setOverrides({});
    setBulk({});
    setError(null);
    setPhase('select');
    if (!selected) return;

    // Validación defensiva antes de subir (el backend también valida).
    const validationError = validateFile(selected);
    if (validationError) {
      setError(validationError);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }
    await runPreview(selected);
  }

  async function handleRevalidate() {
    if (!file || overrideList.length === 0) return;
    await runPreview(file, overrideList);
  }

  function setOverride(
    rowNumber: number,
    field: 'category' | 'supplier' | 'tax',
    value: string,
  ) {
    setOverrides((prev) => {
      const current = { ...(prev[rowNumber] ?? {}) };
      if (value) {
        current[field] = value;
      } else {
        delete current[field];
      }
      const next = { ...prev };
      if (Object.keys(current).length === 0) {
        delete next[rowNumber];
      } else {
        next[rowNumber] = current;
      }
      return next;
    });
  }

  function applySuggestions(row: ImportRow) {
    const fields = unresolvedFields(row);
    setOverrides((prev) => {
      const current = { ...(prev[row.row_number] ?? {}) };
      if (fields.category && row.data.suggested_category) {
        current.category = row.data.suggested_category;
      }
      if (fields.supplier && row.data.suggested_supplier) {
        current.supplier = row.data.suggested_supplier;
      }
      if (fields.tax && row.data.suggested_tax) {
        current.tax = row.data.suggested_tax;
      }
      return { ...prev, [row.row_number]: current };
    });
  }

  function applyBulk() {
    if (!preview) return;
    const fields = (['category', 'supplier', 'tax'] as const).filter(
      (field) => bulk[field],
    );
    if (fields.length === 0) return;
    setOverrides((prev) => {
      const next = { ...prev };
      for (const row of preview.rows) {
        if (row.status !== 'ERROR') continue;
        const unresolved = unresolvedFields(row);
        const current = { ...(next[row.row_number] ?? {}) };
        let changed = false;
        for (const field of fields) {
          if (unresolved[field]) {
            current[field] = bulk[field];
            changed = true;
          }
        }
        if (changed) next[row.row_number] = current;
      }
      return next;
    });
  }

  async function handleConfirm() {
    if (!file || !preview || submitRef.current) return;
    if (importableCount === 0) return;
    submitRef.current = true;
    setBusy(true);
    setError(null);
    setPhase('processing');
    try {
      const res = await confirmImport(file, policy, overrideList);
      setResult({
        batch_id: res?.batch_id ?? '',
        file_name: res?.file_name ?? file.name,
        total_rows: res?.total_rows ?? 0,
        created: res?.created ?? 0,
        updated: res?.updated ?? 0,
        skipped: res?.skipped ?? 0,
        rejected: res?.rejected ?? 0,
        rejected_rows: Array.isArray(res?.rejected_rows)
          ? res.rejected_rows
          : [],
        suppliers_created: res?.suppliers_created ?? 0,
        categories_created: res?.categories_created ?? 0,
      });
      setPhase('result');
    } catch (err) {
      // No se pierde el archivo ni la vista previa: se puede reintentar.
      setError(extractErrorMessage(err));
      setPhase('preview');
    } finally {
      submitRef.current = false;
      setBusy(false);
    }
  }

  async function loadHistory() {
    setBusy(true);
    setError(null);
    try {
      const res = await listImportBatches(0, 50);
      setBatches({
        items: Array.isArray(res?.items) ? res.items : [],
        total: res?.total ?? 0,
        page: res?.page ?? 1,
        size: res?.size ?? 50,
      });
      setPhase('history');
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function downloadErrors(batchId: string) {
    setBusy(true);
    setError(null);
    try {
      const blob = await downloadImportErrors(batchId);
      triggerDownload(blob, `errores_${batchId}.xlsx`);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function resetToSelect() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setOverrides({});
    setBulk({});
    setPhase('select');
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function renderEntitySelect(
    row: ImportRow,
    field: 'category' | 'supplier' | 'tax',
    label: string,
    options: string[],
    suggested: string | null,
  ) {
    const value = overrides[row.row_number]?.[field] ?? '';
    const filtered = options.filter((o) => o !== suggested);
    return (
      <label className="block text-[11px]">
        <span className="text-muted">{label}</span>
        <select
          className="nx-input mt-0.5 w-full text-xs"
          value={value}
          onChange={(e) => setOverride(row.row_number, field, e.target.value)}
        >
          <option value="">Sin cambios</option>
          {suggested && <option value={suggested}>Sugerencia: {suggested}</option>}
          {filtered.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
    );
  }

  return (
    <Modal open onClose={onClose} title="Importar productos desde Excel" wide>
      <div className="space-y-4">
        {error && (
          <div
            role="alert"
            className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
          >
            {error}
          </div>
        )}

        {phase === 'select' && (
          <div className="space-y-3">
            <p className="text-sm text-muted">
              Descarga la plantilla, completa los productos y súbela para
              revisar antes de importar. Nada se guarda hasta que confirmes.
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleDownloadTemplate}
                disabled={busy}
                className="nx-btn nx-btn-secondary"
              >
                <Icon name="download" size={16} />
                Descargar plantilla
              </button>
              <button
                type="button"
                onClick={loadHistory}
                disabled={busy}
                className="nx-btn nx-btn-secondary"
              >
                <Icon name="list" size={16} />
                Ver historial
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.csv"
              onChange={(e) => handleFileSelected(e.target.files?.[0] ?? null)}
              disabled={busy}
              className="block w-full text-sm text-muted file:mr-3 file:rounded file:border-0 file:bg-surface-2 file:px-3 file:py-1.5 file:text-sm"
            />
            {file && (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-muted">Archivo: {file.name}</span>
                <button
                  type="button"
                  onClick={() => runPreview(file, overrideList)}
                  disabled={busy}
                  className="nx-btn nx-btn-primary"
                >
                  Reintentar análisis
                </button>
              </div>
            )}
            {busy && <LoadingState rows={2} />}
          </div>
        )}

        {phase === 'processing' && (
          <div className="space-y-3">
            <p className="text-sm text-muted">Procesando archivo…</p>
            <LoadingState rows={4} />
          </div>
        )}

        {phase === 'preview' && preview && (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2 text-sm">
              <Badge tone="gray">Total: {preview.total_rows}</Badge>
              <Badge tone="green">Válidas: {preview.valid}</Badge>
              <Badge tone="amber">Advertencias: {preview.warnings}</Badge>
              <Badge tone="red">Errores: {preview.errors}</Badge>
            </div>
            <p className="text-xs text-muted">
              Archivo: {preview.file_name}. Se importarán las filas válidas y
              con advertencias; las filas con error se rechazarán y podrás
              descargar su informe.
            </p>

            {entitiesError && (
              <p className="text-xs text-amber-600">
                No se pudieron cargar las categorías/proveedores/impuestos para
                corregir: {entitiesError}. Puedes reintentar el análisis.
              </p>
            )}

            <EntitySummaryPanel preview={preview} />

            {preview.declaration_errors.length > 0 && (
              <div className="rounded border border-amber-500/40 bg-amber-500/10 px-3 py-2">
                <p className="text-xs font-semibold text-amber-700">
                  Avisos en las hojas auxiliares del archivo
                </p>
                <ul className="mt-1 list-disc pl-4 text-xs text-amber-700">
                  {preview.declaration_errors.map((message, index) => (
                    <li key={index}>{message}</li>
                  ))}
                </ul>
              </div>
            )}

            {entities &&
              preview.rows.some(
                (row) =>
                  Object.values(unresolvedFields(row)).some(Boolean),
              ) && (
                <div className="rounded border border-line bg-surface-2/50 p-3">
                  <p className="mb-2 text-xs font-semibold">
                    Asignación masiva a filas con error
                  </p>
                  <div className="grid gap-2 sm:grid-cols-4">
                    <label className="block text-[11px]">
                      <span className="text-muted">Categoría</span>
                      <select
                        className="nx-input mt-0.5 w-full text-xs"
                        value={bulk.category ?? ''}
                        onChange={(e) =>
                          setBulk((prev) => ({
                            ...prev,
                            category: e.target.value || undefined,
                          }))
                        }
                      >
                        <option value="">No aplicar</option>
                        {entities.categories.map((c) => (
                          <option key={c.id} value={c.name}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-[11px]">
                      <span className="text-muted">Proveedor</span>
                      <select
                        className="nx-input mt-0.5 w-full text-xs"
                        value={bulk.supplier ?? ''}
                        onChange={(e) =>
                          setBulk((prev) => ({
                            ...prev,
                            supplier: e.target.value || undefined,
                          }))
                        }
                      >
                        <option value="">No aplicar</option>
                        {entities.suppliers.map((s) => (
                          <option key={s.id} value={s.name}>
                            {s.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-[11px]">
                      <span className="text-muted">Impuesto</span>
                      <select
                        className="nx-input mt-0.5 w-full text-xs"
                        value={bulk.tax ?? ''}
                        onChange={(e) =>
                          setBulk((prev) => ({
                            ...prev,
                            tax: e.target.value || undefined,
                          }))
                        }
                      >
                        <option value="">No aplicar</option>
                        {entities.taxes.map((t) => (
                          <option key={t.id} value={t.name}>
                            {t.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="flex items-end">
                      <button
                        type="button"
                        onClick={applyBulk}
                        disabled={busy || (!bulk.category && !bulk.supplier && !bulk.tax)}
                        className="nx-btn nx-btn-secondary w-full"
                      >
                        Aplicar
                      </button>
                    </div>
                  </div>
                </div>
              )}

            <div className="flex flex-wrap items-center justify-between gap-2">
              <label className="flex items-center gap-2 text-xs text-muted">
                <input
                  type="checkbox"
                  checked={onlyIssues}
                  onChange={(e) => setOnlyIssues(e.target.checked)}
                />
                Mostrar solo filas con errores o advertencias
              </label>
              {overrideList.length > 0 && (
                <button
                  type="button"
                  onClick={handleRevalidate}
                  disabled={busy}
                  className="nx-btn nx-btn-secondary text-xs"
                >
                  <Icon name="refresh" size={14} />
                  Revalidar {overrideList.length} corrección(es)
                </button>
              )}
            </div>

            <div className="max-h-72 overflow-auto rounded border border-line">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-surface-2">
                  <tr>
                    <th className="px-2 py-1">Fila</th>
                    <th className="px-2 py-1">Estado</th>
                    <th className="px-2 py-1">Producto</th>
                    <th className="px-2 py-1">Correcciones</th>
                    <th className="px-2 py-1">Mensajes</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row) => {
                    const fields = unresolvedFields(row);
                    const needsFix = Object.values(fields).some(Boolean);
                    return (
                      <tr key={row.row_number} className="border-t border-line align-top">
                        <td className="px-2 py-1">{row.row_number}</td>
                        <td className="px-2 py-1">
                          <Badge tone={ROW_TONE[row.status]}>
                            {ROW_LABEL[row.status]}
                          </Badge>
                        </td>
                        <td className="px-2 py-1">
                          <div>{row.data.name || '—'}</div>
                          {row.data.barcode && (
                            <div className="text-[11px] text-muted">
                              {row.data.barcode}
                            </div>
                          )}
                        </td>
                        <td className="px-2 py-1">
                          {needsFix && entities ? (
                            <div className="w-44 space-y-1">
                              {fields.category &&
                                renderEntitySelect(
                                  row,
                                  'category',
                                  'Categoría',
                                  entities.categories.map((c) => c.name),
                                  row.data.suggested_category,
                                )}
                              {fields.supplier &&
                                renderEntitySelect(
                                  row,
                                  'supplier',
                                  'Proveedor',
                                  entities.suppliers.map((s) => s.name),
                                  row.data.suggested_supplier,
                                )}
                              {fields.tax &&
                                renderEntitySelect(
                                  row,
                                  'tax',
                                  'Impuesto',
                                  entities.taxes.map((t) => t.name),
                                  row.data.suggested_tax,
                                )}
                              {(row.data.suggested_category ||
                                row.data.suggested_supplier ||
                                row.data.suggested_tax) && (
                                <button
                                  type="button"
                                  onClick={() => applySuggestions(row)}
                                  disabled={busy}
                                  className="text-[11px] text-primary hover:underline"
                                >
                                  Usar coincidencias sugeridas
                                </button>
                              )}
                            </div>
                          ) : (
                            <span className="text-muted">
                              {needsFix
                                ? entitiesError
                                  ? 'No se pudo cargar el catálogo'
                                  : 'Sin coincidencias para corregir'
                                : '—'}
                            </span>
                          )}
                        </td>
                        <td className="px-2 py-1 text-muted">
                          {row.messages.length > 0 ? (
                            <ul className="list-disc pl-4">
                              {row.messages.map((message, index) => (
                                <li key={index}>{message}</li>
                              ))}
                            </ul>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="space-y-1">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="policy"
                  value="SKIP_NEW"
                  checked={policy === 'SKIP_NEW'}
                  onChange={() => setPolicy('SKIP_NEW')}
                />
                Omitir productos ya registrados (recomendado)
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="policy"
                  value="UPDATE_EXISTING"
                  checked={policy === 'UPDATE_EXISTING'}
                  onChange={() => setPolicy('UPDATE_EXISTING')}
                />
                Actualizar el stock y los datos de productos existentes
              </label>
            </div>

            <p className="text-sm text-muted">
              {importableCount > 0
                ? `Se importarán ${importableCount} de ${preview.total_rows} filas.`
                : 'Ninguna fila es importable: corrige los errores antes de confirmar.'}
              {preview.errors > 0 &&
                importableCount > 0 &&
                ` ${preview.errors} fila(s) con error se rechazarán y se incluirán en el informe.`}
            </p>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleConfirm}
                disabled={busy || importableCount === 0}
                className="nx-btn nx-btn-primary"
              >
                {busy ? 'Importando…' : `Confirmar importación (${importableCount})`}
              </button>
              <button
                type="button"
                onClick={resetToSelect}
                disabled={busy}
                className="nx-btn nx-btn-secondary"
              >
                Elegir otro archivo
              </button>
            </div>
          </div>
        )}

        {phase === 'result' && result && (
          <div className="space-y-3">
            {result.created + result.updated + result.skipped > 0 ? (
              <p className="text-sm font-medium text-success">
                Importación completada.
              </p>
            ) : (
              <p className="text-sm font-medium text-amber-600">
                No se importó ningún producto: todas las filas fueron rechazadas.
              </p>
            )}
            <div className="flex flex-wrap gap-2 text-sm">
              <Badge tone="green">Creados: {result.created}</Badge>
              <Badge tone="amber">Actualizados: {result.updated}</Badge>
              <Badge tone="gray">Omitidos: {result.skipped}</Badge>
              <Badge tone="red">Rechazados: {result.rejected}</Badge>
            </div>
            {(result.categories_created > 0 ||
              result.suppliers_created > 0) && (
              <div className="flex flex-wrap gap-2 text-sm">
                <Badge tone="green">
                  Categorías creadas: {result.categories_created}
                </Badge>
                <Badge tone="green">
                  Proveedores creados: {result.suppliers_created}
                </Badge>
              </div>
            )}
            {result.rejected > 0 && (
              <button
                type="button"
                onClick={() => downloadErrors(result.batch_id)}
                disabled={busy}
                className="nx-btn nx-btn-secondary"
              >
                <Icon name="download" size={16} />
                Descargar informe de errores
              </button>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={loadHistory}
                disabled={busy}
                className="nx-btn nx-btn-secondary"
              >
                Ver historial
              </button>
              <button
                type="button"
                onClick={resetToSelect}
                disabled={busy}
                className="nx-btn nx-btn-secondary"
              >
                Importar otro archivo
              </button>
              <button
                type="button"
                onClick={onClose}
                className="nx-btn nx-btn-primary"
              >
                Cerrar
              </button>
            </div>
          </div>
        )}

        {phase === 'history' && (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold">Historial de lotes</h3>
            {batches && batches.items.length > 0 ? (
              <div className="max-h-64 overflow-auto rounded border border-line">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-surface-2">
                    <tr>
                      <th className="px-2 py-1">Archivo</th>
                      <th className="px-2 py-1">Fecha</th>
                      <th className="px-2 py-1">Creados</th>
                      <th className="px-2 py-1">Actualizados</th>
                      <th className="px-2 py-1">Omitidos</th>
                      <th className="px-2 py-1">Rechazados</th>
                      <th className="px-2 py-1">Errores</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batches.items.map((b) => (
                      <tr key={b.id} className="border-t border-line">
                        <td className="px-2 py-1">{b.file_name}</td>
                        <td className="px-2 py-1">
                          {formatDateTime(b.created_at)}
                        </td>
                        <td className="px-2 py-1">{b.created_count}</td>
                        <td className="px-2 py-1">{b.updated_count}</td>
                        <td className="px-2 py-1">{b.skipped_count}</td>
                        <td className="px-2 py-1">{b.rejected_count}</td>
                        <td className="px-2 py-1">
                          {b.rejected_count > 0 ? (
                            <button
                              type="button"
                              onClick={() => downloadErrors(b.id)}
                              disabled={busy}
                              className="text-primary hover:underline"
                            >
                              Descargar
                            </button>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted">Aún no hay lotes importados.</p>
            )}
            <button
              type="button"
              onClick={resetToSelect}
              disabled={busy}
              className="nx-btn nx-btn-secondary"
            >
              Nueva importación
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
}
