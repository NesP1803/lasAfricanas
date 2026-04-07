export type DocumentTypeKey =
  | 'FACTURA_VENTA'
  | 'NOTA_CREDITO'
  | 'NOTA_DEBITO'
  | 'DOCUMENTO_SOPORTE'
  | 'NOTA_AJUSTE_DOCUMENTO_SOPORTE'
  | 'NOMINA'
  | 'NOTA_AJUSTE_NOMINA'
  | 'FACTURA_TALONARIO_O_PAPEL';

export const DOCUMENT_TYPES: Array<{ key: DocumentTypeKey; label: string; factusCode: string }> = [
  { key: 'FACTURA_VENTA', label: 'Factura de Venta', factusCode: '21' },
  { key: 'NOTA_CREDITO', label: 'Nota Crédito', factusCode: '22' },
  { key: 'NOTA_DEBITO', label: 'Nota Débito', factusCode: '23' },
  { key: 'DOCUMENTO_SOPORTE', label: 'Documento Soporte', factusCode: '24' },
  { key: 'NOTA_AJUSTE_DOCUMENTO_SOPORTE', label: 'Nota de Ajuste Documento Soporte', factusCode: '25' },
  { key: 'NOMINA', label: 'Nómina', factusCode: '26' },
  { key: 'NOTA_AJUSTE_NOMINA', label: 'Nota de Ajuste Nómina', factusCode: '27' },
  { key: 'FACTURA_TALONARIO_O_PAPEL', label: 'Factura de talonario o de papel', factusCode: '30' },
];

export const ADMIN_RANGE_DOCUMENT_TYPES = DOCUMENT_TYPES.filter((item) =>
  ['FACTURA_VENTA', 'NOTA_CREDITO', 'NOTA_DEBITO', 'DOCUMENTO_SOPORTE', 'NOTA_AJUSTE_DOCUMENTO_SOPORTE'].includes(item.key)
);
