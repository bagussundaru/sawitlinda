"use client";

import { useState } from "react";

import { imageFileUrl } from "@/lib/api";
import { SEVERITY_COLOR, isHealthy } from "@/lib/severity";
import type { Detection } from "@/types/detection";

/** The uploaded frame with detection boxes drawn over it.
 *
 * The overlay is an SVG sized to the image's natural pixel dimensions, so boxes
 * land correctly whatever the rendered size — the browser scales both together.
 */
export default function AnnotatedImage({
  imageId,
  filename,
  detections,
  highlighted,
  onHighlight,
  showLabels = true,
}: {
  imageId: string;
  filename: string;
  detections: Detection[];
  highlighted?: number | null;
  onHighlight?: (id: number | null) => void;
  showLabels?: boolean;
}) {
  const [size, setSize] = useState({ width: 0, height: 0 });

  return (
    <div className="relative overflow-hidden rounded-[12px] border border-[var(--line)] bg-[#2f5a2f]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={imageFileUrl(imageId)}
        alt={`Citra UAV ${filename}`}
        className="block w-full"
        onLoad={(event) =>
          setSize({
            width: event.currentTarget.naturalWidth,
            height: event.currentTarget.naturalHeight,
          })
        }
      />
      {size.width > 0 && (
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox={`0 0 ${size.width} ${size.height}`}
          preserveAspectRatio="none"
        >
          {detections.map((detection) => {
            const [x, y, w, h] = detection.bbox;
            const color = SEVERITY_COLOR[detection.severity];

            if (isHealthy(detection.severity)) {
              return (
                <circle
                  key={detection.id}
                  cx={x + w / 2}
                  cy={y + h / 2}
                  r={Math.max(3, size.width / 220)}
                  fill={color}
                  opacity={0.75}
                />
              );
            }

            const active = highlighted === detection.id;
            const labelHeight = size.height / 34;
            return (
              <g
                key={detection.id}
                style={{ cursor: onHighlight ? "pointer" : "default" }}
                onMouseEnter={() => onHighlight?.(detection.id)}
                onMouseLeave={() => onHighlight?.(null)}
              >
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  fill="none"
                  stroke={color}
                  strokeWidth={active ? 5 : 2.5}
                  rx={3}
                />
                {showLabels && (
                  <>
                    <rect
                      x={x}
                      y={y - labelHeight}
                      width={labelHeight * 2.6}
                      height={labelHeight}
                      fill={color}
                    />
                    <text
                      x={x + labelHeight * 0.25}
                      y={y - labelHeight * 0.25}
                      fill="#fff"
                      fontSize={labelHeight * 0.7}
                      fontFamily="sans-serif"
                    >
                      {(detection.confidence * 100).toFixed(0)}%
                    </text>
                  </>
                )}
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}
