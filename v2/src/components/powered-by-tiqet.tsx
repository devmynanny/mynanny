import Image from "next/image";

export function PoweredByTiqet({ className = "" }: { className?: string }) {
  return (
    <a
      href="https://tiqet.co.za"
      aria-label="Powered by TIQET"
      className={`inline-flex shrink-0 items-center ${className}`}
      target="_blank"
      rel="noreferrer"
    >
      <Image
        src="/brand/powered-by-tiqet.svg"
        alt="Powered by TIQET"
        width={240}
        height={87}
        className="h-auto w-[210px] sm:w-[240px]"
      />
    </a>
  );
}
