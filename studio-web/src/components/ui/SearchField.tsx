import type { InputHTMLAttributes } from "react";

export function SearchField({ value, onChange, placeholder = "Search", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <label className="ds-search-field"><span className="sr-only">Search</span><input {...props} type="search" value={value} onChange={onChange} placeholder={placeholder} /></label>;
}
