"use client";

import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import { useEffect } from "react";

import type { MapImagePoint, VillageInfo } from "@/types/detection";

/** Zoom tertinggi yang tersedia pada ubin OpenStreetMap.
 *
 *  Dikunci karena `fitBounds` pada citra yang berdekatan memilih zoom melebihi
 *  batas ini — dan Leaflet lalu menyembunyikan SELURUH lapisan peta, menyisakan
 *  titik di atas latar kosong. */
const MAX_ZOOM = 19;

/** Warna penanda mengikuti bagian pohon yang bermasalah pada citra itu. */
function warna(share: number): string {
  if (share >= 0.35) return "var(--severe)";
  if (share >= 0.15) return "var(--mild)";
  return "var(--healthy)";
}

function bounds(points: MapImagePoint[]): [[number, number], [number, number]] {
  const lats = points.map((p) => p.gps.lat);
  const lngs = points.map((p) => p.gps.lng);
  return [
    [Math.min(...lats), Math.min(...lngs)],
    [Math.max(...lats), Math.max(...lngs)],
  ];
}

/** Geser tampilan saat pilihan desa berubah.
 *
 *  Dibuat sebagai komponen anak karena `useMap` hanya tersedia di dalam
 *  MapContainer — instance peta belum ada di komponen induk. */
function Pindah({
  points,
  centre,
}: {
  points: MapImagePoint[];
  centre: [number, number] | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (points.length > 0) {
      map.fitBounds(bounds(points), { padding: [48, 48], maxZoom: MAX_ZOOM });
    } else if (centre) {
      map.setView(centre, 11);
    }
  }, [map, points, centre]);

  return null;
}

export default function PlantationMap({
  points,
  villages,
  selectedVillage,
  selectedId,
  onSelect,
  height = 460,
}: {
  points: MapImagePoint[];
  villages: VillageInfo[];
  selectedVillage: string | null;
  selectedId?: string | null;
  onSelect?: (point: MapImagePoint) => void;
  height?: number;
}) {
  const village = villages.find((v) => v.key === selectedVillage) ?? null;

  // Tampilan awal: pusat desa terpilih, atau pusat kabupaten. Ini SEMATA
  // penempatan kamera — tidak ada penanda yang digambar di titik ini.
  const centre: [number, number] = village
    ? [village.lat, village.lng]
    : [-2.45, 112.9];

  return (
    <div className="overflow-hidden rounded-[14px] border border-[var(--line)]">
      <MapContainer
        center={centre}
        zoom={10}
        maxZoom={MAX_ZOOM}
        scrollWheelZoom
        style={{ height, width: "100%" }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap"
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={MAX_ZOOM}
        />
        <Pindah points={points} centre={village ? centre : null} />

        {points.map((point) => {
          const active = selectedId === point.image_id;
          const c = warna(point.affected_share);
          return (
            <CircleMarker
              key={point.image_id}
              center={[point.gps.lat, point.gps.lng]}
              radius={active ? 13 : 9}
              eventHandlers={onSelect ? { click: () => onSelect(point) } : undefined}
              pathOptions={{
                color: active ? "#08301F" : c,
                fillColor: c,
                fillOpacity: 0.88,
                weight: active ? 3 : 1.5,
              }}
            >
              <Popup>
                <b>{point.label ?? point.filename}</b>
                <br />
                {point.summary.total} trees · {point.summary.infected} affected
                <br />
                {point.dominant_condition && (
                  <>
                    Dominant: {point.dominant_condition}
                    <br />
                  </>
                )}
                <span className="mono">
                  {point.gps.lat.toFixed(5)}, {point.gps.lng.toFixed(5)}
                </span>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
