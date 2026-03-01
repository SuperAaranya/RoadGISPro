#!/usr/bin/env node

function segmentLength(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length < 2 || b.length < 2) {
    return 0;
  }
  const dx = Number(b[0]) - Number(a[0]);
  const dy = Number(b[1]) - Number(a[1]);
  if (!Number.isFinite(dx) || !Number.isFinite(dy)) {
    return 0;
  }
  return Math.hypot(dx, dy);
}

function computeMetrics(payload) {
  const roads = Array.isArray(payload.roads) ? payload.roads : [];
  const connectors = Array.isArray(payload.connectors) ? payload.connectors : [];

  let totalLen = 0;
  let totalSpeed = 0;
  let totalLanes = 0;
  let onewayCount = 0;

  for (const road of roads) {
    if (!road || typeof road !== "object") continue;
    const geom = Array.isArray(road.geom) ? road.geom : [];
    for (let i = 0; i < geom.length - 1; i += 1) {
      totalLen += segmentLength(geom[i], geom[i + 1]);
    }
    const speed = Number(road.speed || 0);
    const lanes = Number(road.lanes || 0);
    totalSpeed += Number.isFinite(speed) ? speed : 0;
    totalLanes += Number.isFinite(lanes) ? lanes : 0;
    if (road.oneway) onewayCount += 1;
  }

  const roadCount = roads.length;
  return {
    engine: "javascript",
    road_count: roadCount,
    connector_count: connectors.length,
    total_length_km: totalLen / 1000,
    average_speed_limit: roadCount ? totalSpeed / roadCount : 0,
    average_lanes: roadCount ? totalLanes / roadCount : 0,
    oneway_share: roadCount ? onewayCount / roadCount : 0,
  };
}

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  const payload = raw.trim() ? JSON.parse(raw) : {};
  const result = computeMetrics(payload);
  process.stdout.write(JSON.stringify(result));
}

main().catch((err) => {
  process.stderr.write(String(err) + "\n");
  process.exit(1);
});
