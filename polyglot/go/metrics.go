package main

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
)

type Payload struct {
	Roads      []map[string]interface{} `json:"roads"`
	Connectors []interface{}            `json:"connectors"`
}

func toFloat(v interface{}) (float64, bool) {
	switch n := v.(type) {
	case float64:
		return n, true
	case float32:
		return float64(n), true
	case int:
		return float64(n), true
	case int64:
		return float64(n), true
	default:
		return 0, false
	}
}

func segmentLength(a, b interface{}) float64 {
	pa, oka := a.([]interface{})
	pb, okb := b.([]interface{})
	if !oka || !okb || len(pa) < 2 || len(pb) < 2 {
		return 0
	}
	ax, oka := toFloat(pa[0])
	ay, okb := toFloat(pa[1])
	bx, okc := toFloat(pb[0])
	by, okd := toFloat(pb[1])
	if !(oka && okb && okc && okd) {
		return 0
	}
	return math.Hypot(bx-ax, by-ay)
}

func main() {
	raw, err := io.ReadAll(os.Stdin)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var payload Payload
	if len(raw) > 0 {
		if err := json.Unmarshal(raw, &payload); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}

	totalLen := 0.0
	totalSpeed := 0.0
	totalLanes := 0.0
	onewayCount := 0
	roadCount := len(payload.Roads)

	for _, road := range payload.Roads {
		if speed, ok := toFloat(road["speed"]); ok {
			totalSpeed += speed
		}
		if lanes, ok := toFloat(road["lanes"]); ok {
			totalLanes += lanes
		}
		if oneway, ok := road["oneway"].(bool); ok && oneway {
			onewayCount++
		}
		geom, ok := road["geom"].([]interface{})
		if !ok {
			continue
		}
		for i := 0; i < len(geom)-1; i++ {
			totalLen += segmentLength(geom[i], geom[i+1])
		}
	}

	avgSpeed := 0.0
	avgLanes := 0.0
	onewayShare := 0.0
	if roadCount > 0 {
		avgSpeed = totalSpeed / float64(roadCount)
		avgLanes = totalLanes / float64(roadCount)
		onewayShare = float64(onewayCount) / float64(roadCount)
	}

	result := map[string]interface{}{
		"engine":              "go",
		"road_count":          roadCount,
		"connector_count":     len(payload.Connectors),
		"total_length_km":     totalLen / 1000.0,
		"average_speed_limit": avgSpeed,
		"average_lanes":       avgLanes,
		"oneway_share":        onewayShare,
	}
	out, _ := json.Marshal(result)
	fmt.Println(string(out))
}
