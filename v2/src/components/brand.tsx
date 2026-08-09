import Image from "next/image";
import Link from "next/link";

export function Brand({
  compact = false,
  large = false,
}: {
  compact?: boolean;
  large?: boolean;
}) {
  const dimensions = large
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
          className="object-contain object-left"
          priority
        />
      </span>
    </Link>
  );
}
