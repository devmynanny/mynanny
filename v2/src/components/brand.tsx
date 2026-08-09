import Image from "next/image";
import Link from "next/link";

export function Brand({
  compact = false,
  large = false,
  home = false,
  sidebar = false,
}: {
  compact?: boolean;
  large?: boolean;
  home?: boolean;
  sidebar?: boolean;
}) {
  const dimensions = home
    ? {
        className:
          "relative block h-20 w-[212px] sm:h-28 sm:w-[298px]",
        sizes: "(min-width: 640px) 298px, 212px",
      }
    : sidebar
    ? { className: "relative block h-[84px] w-56", sizes: "224px" }
    : large
    ? { className: "relative block h-24 w-[255px]", sizes: "255px" }
    : compact
      ? { className: "relative block h-10 w-[106px]", sizes: "106px" }
      : { className: "relative block h-14 w-[149px]", sizes: "149px" };
  return (
    <Link
      href="/"
      aria-label="My Nanny home"
      className="inline-flex items-center"
    >
      <span className={dimensions.className}>
        <Image
          src="/logo.jpg"
          alt="My Nanny"
          fill
          sizes={dimensions.sizes}
          className="mix-blend-multiply object-contain object-left"
          priority
        />
      </span>
    </Link>
  );
}
