package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
)

type Payload struct {
	Roads []map[string]interface{} `json:"roads"`
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

	byType := map[string]int{}
	bridges := 0
	tunnels := 0
	for _, road := range payload.Roads {
		if rtype, ok := road["rtype"].(string); ok && rtype != "" {
			byType[rtype]++
		} else {
			byType["unknown"]++
		}
		if tunnel, ok := road["tunnel"].(bool); ok && tunnel {
			tunnels++
		}
		if lvl, ok := road["bridge_level"].(float64); ok && int(lvl) > 0 {
			bridges++
		}
	}
	out := map[string]interface{}{
		"plugin_kind":     "network_health",
		"road_type_counts": byType,
		"bridge_features": bridges,
		"tunnel_features": tunnels,
	}
	buf, _ := json.Marshal(out)
	fmt.Println(string(buf))
}
