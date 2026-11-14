import type { Metadata } from "next";
import { BureauShell } from "@/components/bureau/shell";

export const metadata: Metadata = { title: "Bureau console", robots: { index: false, follow: false } };

export default function BureauLayout({ children }: LayoutProps<"/[locale]/bureau">) {
  return <BureauShell>{children}</BureauShell>;
}
