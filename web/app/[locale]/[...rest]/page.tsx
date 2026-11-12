import { notFound } from "next/navigation";

// Any unmatched path under a locale renders the localized not-found page (inside the
// [locale] layout, so <html lang> and site chrome are preserved).
export default function CatchAll() {
  notFound();
}
