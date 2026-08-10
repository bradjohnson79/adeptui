import type { ReactNode } from "react";
import "./table.css";

export type DataTableColumn<T> = { key: string; header: ReactNode; render?: (row: T) => ReactNode; sortable?: boolean };
export type DataTableProps<T> = { columns: DataTableColumn<T>[]; rows: T[]; rowKey?: (row: T, index: number) => string; sortKey?: string; sortDirection?: "ascending" | "descending" | "none"; onSort?: (key: string) => void; empty?: ReactNode; className?: string };

export function SortButton({ children, active = false, direction = "none", onClick }: { children: ReactNode; active?: boolean; direction?: "ascending" | "descending" | "none"; onClick?: () => void }) {
  return <button type="button" className="ds-table__sort" aria-sort={active ? direction : "none"} onClick={onClick}>{children}{active ? <span aria-hidden>{direction === "ascending" ? " ↑" : " ↓"}</span> : null}</button>;
}

export function DataTable<T>({ columns, rows, rowKey, sortKey, sortDirection = "none", onSort, empty = "No results.", className = "" }: DataTableProps<T>) {
  return <div className={["ds-table-container", className].filter(Boolean).join(" ")}><table className="ds-table"><thead><tr>{columns.map((column) => <th key={column.key} scope="col" aria-sort={sortKey === column.key ? sortDirection : "none"}>{column.sortable ? <SortButton active={sortKey === column.key} direction={sortDirection} onClick={() => onSort?.(column.key)}>{column.header}</SortButton> : column.header}</th>)}</tr></thead><tbody>{rows.length ? rows.map((row, index) => <tr key={rowKey?.(row, index) ?? String(index)}>{columns.map((column) => <td key={column.key}>{column.render ? column.render(row) : String((row as unknown as Record<string, unknown>)[column.key] ?? "")}</td>)}</tr>) : <tr><td colSpan={columns.length}>{empty}</td></tr>}</tbody></table></div>;
}

export function Pagination({ page, pageCount, onPageChange }: { page: number; pageCount: number; onPageChange: (page: number) => void }) {
  return <nav className="ds-pagination" aria-label="Pagination"><button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Previous</button><span>Page {page} of {pageCount}</span><button type="button" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}>Next</button></nav>;
}
