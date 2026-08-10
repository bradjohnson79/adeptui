import type { ReactNode } from "react";
import { Button } from "./Button";
import { SearchField } from "./SearchField";
import "./table.css";

export function ListToolbar({ search, onSearchChange, filters, count, onRefresh, busy = false }: { search?: string; onSearchChange?: (value: string) => void; filters?: ReactNode; count?: ReactNode; onRefresh?: () => void; busy?: boolean }) {
  return <div className="ds-list-toolbar">{onSearchChange ? <SearchField value={search ?? ""} onChange={(event) => onSearchChange(event.target.value)} /> : null}<div className="ds-list-toolbar__filters">{filters}</div>{count !== undefined ? <span className="ds-list-toolbar__count">{count}</span> : null}{onRefresh ? <Button variant="ghost" compact onClick={onRefresh} loading={busy}>Refresh</Button> : null}</div>;
}
