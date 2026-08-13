import ResultScreen from "./ResultScreen";

export default async function HasilPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ResultScreen imageId={id} />;
}
