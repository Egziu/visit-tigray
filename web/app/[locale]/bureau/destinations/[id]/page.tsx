import { DestinationEditor } from "@/components/bureau/content-tools";

export default async function Page({ params }: PageProps<"/[locale]/bureau/destinations/[id]">) {
  const { id } = await params;
  return <DestinationEditor id={id} />;
}
