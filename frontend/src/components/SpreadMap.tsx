"use client";

import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";

import { SEVERITY_COLOR, isHealthy } from "@/lib/severity";
import type { MapPoint } from "@/types/detection";

/** Highest zoom the OpenStreetMap tiles are available at. */
const MAX_ZOOM = 19;

function bounds(points: MapPoint[]): [[number, number], [number, number]] {
  const lats = points.map((point) => point.gps.lat);
  const lngs = points.map((point) => point.gps.lng);
  return [
    [Math.min(...lats), Math.min(...lngs)],
    [Math.max(...lats), Math.max(...lngs)],
  ];
}

export default function SpreadMap({
  points,
  height = 372,
  selectedId,
  onSelect,
}: {
  points: MapPoint[];
  height?: number;
  selectedId?: number | null;
  onSelect?: (point: MapPoint) => void;
}) {
  return (
    <div className="overflow-hidden rounded-[14px] border border-[var(--line)]">
      <MapContainer
        bounds={bounds(points)}
        boundsOptions={{ padding: [40, 40] }}
        // Trees in one block sit metres apart, so fitBounds would otherwise pick a
        // zoom beyond what the tiles go to — at which point Leaflet hides the whole
        // tile layer and the map renders blank behind the points.
        maxZoom={MAX_ZOOM}
        scrollWheelZoom
        style={{ height, width: "100%" }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap"
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={MAX_ZOOM}
        />
        {points.map((point) => {
          const healthy = isHealthy(point.severity);
          const color = SEVERITY_COLOR[point.severity];
          const active = selectedId === point.detection_id;
          return (
            <CircleMarker
              key={`${point.image_id}-${point.detection_id}`}
              center={[point.gps.lat, point.gps.lng]}
              radius={active ? 10 : healthy ? 4 : 7}
              eventHandlers={onSelect ? { click: () => onSelect(point) } : undefined}
              pathOptions={{
                color: active ? "#08301F" : color,
                fillColor: color,
                fillOpacity: healthy ? 0.6 : 0.92,
                weight: active ? 3 : healthy ? 1 : 2,
              }}
            >
              <Popup>
                <b>{point.condition}</b>
                <br />
                Keparahan: {point.severity}
                <br />
                Keyakinan: {(point.confidence * 100).toFixed(1)}%
                <br />
                <span className="mono">
                  {point.gps.lat.toFixed(5)}, {point.gps.lng.toFixed(5)}
                </span>
                <br />
                <span className="text-[var(--muted)]">{point.filename}</span>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
