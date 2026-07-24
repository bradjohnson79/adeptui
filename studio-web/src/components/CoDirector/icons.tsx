import type { ReactNode, SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { title?: string };

function Base({ title, children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined}
      {...props}
    >
      {title ? <title>{title}</title> : null}
      {children}
    </svg>
  );
}

export function IconPaperclip(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M21.44 11.05l-8.49 8.49a5.5 5.5 0 01-7.78-7.78l8.49-8.49a3.5 3.5 0 014.95 4.95l-8.49 8.49a1.5 1.5 0 01-2.12-2.12l7.78-7.78" />
    </Base>
  );
}

export function IconGallery(props: IconProps) {
  return (
    <Base {...props}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <circle cx="9" cy="10" r="1.5" />
      <path d="M21 16l-5-5-4 4-2-2-5 5" />
    </Base>
  );
}

export function IconMic(props: IconProps) {
  return (
    <Base {...props}>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0014 0M12 18v3M8 21h8" />
    </Base>
  );
}

export function IconSend(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M22 2L11 13" />
      <path d="M22 2l-7 20-4-9-9-4 20-7z" />
    </Base>
  );
}

export function IconExpand(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M9 3H3v6M15 3h6v6M9 21H3v-6M21 15v6h-6" />
    </Base>
  );
}

export function IconCollapse(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M9 9H3V3M15 9h6V3M9 15H3v6M21 15v6h-6" />
    </Base>
  );
}

export function IconClose(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M18 6L6 18M6 6l12 12" />
    </Base>
  );
}

export function IconOverflow(props: IconProps) {
  return (
    <Base {...props}>
      <circle cx="12" cy="5" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="12" cy="19" r="1.5" fill="currentColor" stroke="none" />
    </Base>
  );
}

export function IconCoDirector(props: IconProps) {
  return (
    <Base {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8 13c1.2 1.5 2.5 2.2 4 2.2s2.8-.7 4-2.2" />
      <circle cx="9" cy="10" r="1" fill="currentColor" stroke="none" />
      <circle cx="15" cy="10" r="1" fill="currentColor" stroke="none" />
    </Base>
  );
}
