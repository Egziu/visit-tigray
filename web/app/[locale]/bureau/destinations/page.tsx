import { DestinationsList } from "@/components/bureau/content-tools";

export default async function Page({ searchParams }: PageProps<"/[locale]/bureau/destinations">) {
  const sp = await searchParams;
  return <DestinationsList startNew={sp.new === "1"} />;
}
