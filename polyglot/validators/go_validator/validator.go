package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
)

type Payload struct {
	Roads      []map[string]interface{} `json:"roads"`
	Connectors []map[string]interface{} `json:"connectors"`
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

	issues := []string{}
	for i, road := range payload.Roads {
		geom, ok := road["geom"].([]interface{})
		if !ok || len(geom) < 2 {
			issues = append(issues, fmt.Sprintf("road[%d] has invalid geometry", i))
		}
		if _, ok := road["name"]; !ok {
			issues = append(issues, fmt.Sprintf("road[%d] missing name", i))
		}
	}
	for i, conn := range payload.Connectors {
		for _, side := range []string{"a", "b"} {
			node, ok := conn[side].([]interface{})
			if !ok || len(node) != 3 {
				issues = append(issues, fmt.Sprintf("connector[%d].%s invalid node", i, side))
			}
		}
	}

	out := map[string]interface{}{
		"engine": "go-validator",
		"issues": issues,
	}
	buf, _ := json.Marshal(out)
	fmt.Println(string(buf))
}
