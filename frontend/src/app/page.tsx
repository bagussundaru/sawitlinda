export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-4 px-6">
      <h1 className="text-3xl font-semibold">SawitScan AI</h1>
      <p className="text-neutral-600">
        Deteksi &amp; klasifikasi penyakit kelapa sawit dari citra UAV.
      </p>
      <p className="text-sm text-neutral-500">
        Kerangka proyek (tahap 1). Layar unggah, hasil deteksi, dashboard, dan peta
        dibangun pada tahap berikutnya mengikuti prototype.
      </p>
    </main>
  );
}
