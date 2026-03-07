"use client";
import { useMemo } from "react";

interface Props {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}

export default function Sparkline({ data, width = 80, height = 28, color }: Props) {
  const path = useMemo(() => {
    if (data.length < 2) return "";
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const scaleX = width / (data.length - 1);
    const scaleY = (height - 4) / range;
    return data
      .map((v, i) => {
        const x = i * scaleX;
        const y = height - 2 - (v - min) * scaleY;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [data, width, height]);

  const lineColor =
    color ??
    (data.length >= 2
      ? data[data.length - 1] >= data[0]
        ? "#00c853"
        : "#ff5252"
      : "#8b949e");

  if (!path) return <div style={{ width, height }} />;

  return (
    <svg width={width} height={height} style={{ overflow: "visible" }}>
      <path d={path} fill="none" stroke={lineColor} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}
