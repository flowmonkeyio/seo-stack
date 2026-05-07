// Shared type aliases for component props.

export type DataTableColumn<T> = {
  key: keyof T & string
  label: string
  sortable?: boolean
  format?: (value: unknown, row: T) => string
  /** Optional CSS classes applied to the <td> for this column. */
  cellClass?: string
  /** Optional width hint (e.g. "w-32"). */
  widthClass?: string
}

export type DataTableSortDir = 'asc' | 'desc' | null
