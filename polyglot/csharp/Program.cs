using System.Text.Json;

static double SegmentLength(JsonElement a, JsonElement b)
{
    if (a.ValueKind != JsonValueKind.Array || b.ValueKind != JsonValueKind.Array)
        return 0;
    if (a.GetArrayLength() < 2 || b.GetArrayLength() < 2)
        return 0;
    if (!a[0].TryGetDouble(out var ax) || !a[1].TryGetDouble(out var ay))
        return 0;
    if (!b[0].TryGetDouble(out var bx) || !b[1].TryGetDouble(out var by))
        return 0;
    return Math.Sqrt((bx - ax) * (bx - ax) + (by - ay) * (by - ay));
}

var input = Console.In.ReadToEnd();
using var doc = string.IsNullOrWhiteSpace(input)
    ? JsonDocument.Parse("{}")
    : JsonDocument.Parse(input);

var root = doc.RootElement;
var roads = root.TryGetProperty("roads", out var roadsEl) && roadsEl.ValueKind == JsonValueKind.Array
    ? roadsEl
    : default;
var connectors = root.TryGetProperty("connectors", out var connEl) && connEl.ValueKind == JsonValueKind.Array
    ? connEl
    : default;

double totalLen = 0;
double totalSpeed = 0;
double totalLanes = 0;
int onewayCount = 0;
int roadCount = roads.ValueKind == JsonValueKind.Array ? roads.GetArrayLength() : 0;

if (roads.ValueKind == JsonValueKind.Array)
{
    foreach (var road in roads.EnumerateArray())
    {
        if (road.TryGetProperty("speed", out var speed) && speed.TryGetDouble(out var sv))
            totalSpeed += sv;
        if (road.TryGetProperty("lanes", out var lanes) && lanes.TryGetDouble(out var lv))
            totalLanes += lv;
        if (road.TryGetProperty("oneway", out var oneway) && oneway.ValueKind == JsonValueKind.True)
            onewayCount++;

        if (road.TryGetProperty("geom", out var geom) && geom.ValueKind == JsonValueKind.Array)
        {
            var pts = geom.EnumerateArray().ToArray();
            for (int i = 0; i < pts.Length - 1; i++)
                totalLen += SegmentLength(pts[i], pts[i + 1]);
        }
    }
}

double avgSpeed = roadCount > 0 ? totalSpeed / roadCount : 0;
double avgLanes = roadCount > 0 ? totalLanes / roadCount : 0;
double onewayShare = roadCount > 0 ? (double)onewayCount / roadCount : 0;
int connectorCount = connectors.ValueKind == JsonValueKind.Array ? connectors.GetArrayLength() : 0;

var result = new
{
    engine = "csharp",
    road_count = roadCount,
    connector_count = connectorCount,
    total_length_km = totalLen / 1000.0,
    average_speed_limit = avgSpeed,
    average_lanes = avgLanes,
    oneway_share = onewayShare
};

Console.WriteLine(JsonSerializer.Serialize(result));
