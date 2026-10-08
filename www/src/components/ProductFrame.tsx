type ProductFrameProps = {
  src: string;
  alt: string;
  width: number;
  height: number;
  caption?: string;
  eager?: boolean;
  className?: string;
};

export function ProductFrame({ src, alt, width, height, caption, eager = false, className }: ProductFrameProps) {
  return (
    <figure className={className ? `shot ${className}` : "shot"}>
      <div className="shot__plate">
        <img
          src={src}
          alt={alt}
          width={width}
          height={height}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          {...(eager ? { fetchPriority: "high" as const } : {})}
        />
      </div>
      {caption ? <figcaption>{caption}</figcaption> : null}
    </figure>
  );
}

type FilmStillProps = {
  src: string;
  alt: string;
  width: number;
  height: number;
  caption: string;
};

export function FilmStill({ src, alt, width, height, caption }: FilmStillProps) {
  return (
    <figure className="film">
      <img src={src} alt={alt} width={width} height={height} loading="lazy" decoding="async" />
      <figcaption>{caption}</figcaption>
    </figure>
  );
}
