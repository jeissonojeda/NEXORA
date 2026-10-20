export interface ApiTaxBrief {
  id: string;
  name: string;
  rate: string;
}

export interface ApiTax extends ApiTaxBrief {
  description: string | null;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface TaxFormValues {
  name: string;
  rate: string;
  description: string;
  is_active: boolean;
  is_default: boolean;
}

export interface ApiCurrency {
  code: string;
  name: string;
  symbol: string;
  locale: string;
  decimals: number;
}

export interface ApiSettings {
  id: number;
  currency_code: string;
  currency_symbol: string;
  currency_locale: string;
  decimal_places: number;
  use_thousand_separator: boolean;
  business_name: string;
  business_tax_id: string | null;
  business_address: string | null;
  business_phone: string | null;
  business_email: string | null;
  business_logo_path: string | null;
  business_legal_name: string | null;
  business_header_text: string | null;
  business_additional_info: string | null;
  printer_name: string | null;
  paper_width: string;
  print_copies: number;
  print_font_size: string;
  print_show_logo: boolean;
  print_show_contact: boolean;
  print_show_tax_id: boolean;
  print_footer_text: string | null;
  print_logo_size: string | null;
  print_logo_align: string | null;
  print_show_company_name: boolean;
  print_show_nit: boolean;
  print_show_address: boolean;
  print_show_phone: boolean;
  print_show_email: boolean;
  print_show_city: boolean;
  print_show_header_text: boolean;
  print_show_additional_info: boolean;
  print_show_legal_footer: boolean;
  print_show_customer_info: boolean;
  print_show_seller: boolean;
  print_show_payment_method: boolean;
  print_show_sale_date: boolean;
  print_show_due_date: boolean;
  print_show_barcode: boolean;
  print_show_unit: boolean;
  print_show_discount: boolean;
  print_show_tax: boolean;
  print_alignment: string | null;
  print_margin_mm: number | null;
  logo_filename: string | null;
  logo_mime_type: string | null;
  logo_size_bytes: number | null;
  updated_at: string;
}

export interface SettingsUpdatePayload {
  currency_code?: string;
  currency_symbol?: string;
  currency_locale?: string;
  decimal_places?: number;
  use_thousand_separator?: boolean;
  business_name?: string;
  business_tax_id?: string | null;
  business_address?: string | null;
  business_phone?: string | null;
  business_email?: string | null;
  business_logo_path?: string | null;
  business_legal_name?: string | null;
  business_header_text?: string | null;
  business_additional_info?: string | null;
  printer_name?: string | null;
  paper_width?: string;
  print_copies?: number;
  print_font_size?: string;
  print_show_logo?: boolean;
  print_show_contact?: boolean;
  print_show_tax_id?: boolean;
  print_footer_text?: string | null;
  print_logo_size?: string | null;
  print_logo_align?: string | null;
  print_show_company_name?: boolean;
  print_show_nit?: boolean;
  print_show_address?: boolean;
  print_show_phone?: boolean;
  print_show_email?: boolean;
  print_show_city?: boolean;
  print_show_header_text?: boolean;
  print_show_additional_info?: boolean;
  print_show_legal_footer?: boolean;
  print_show_customer_info?: boolean;
  print_show_seller?: boolean;
  print_show_payment_method?: boolean;
  print_show_sale_date?: boolean;
  print_show_due_date?: boolean;
  print_show_barcode?: boolean;
  print_show_unit?: boolean;
  print_show_discount?: boolean;
  print_show_tax?: boolean;
  print_alignment?: string | null;
  print_margin_mm?: number | null;
  confirm_currency_change?: boolean;
}
