use serde::Deserialize;
use serde::Serialize;
use serde_json::Value;
use std::io::{self, Read};

#[derive(Deserialize)]
struct Payload {
    roads: Option<Vec<Value>>,
    connectors: Option<Vec<Value>>,
}

#[derive(Serialize)]
struct Output {
    engine: &'static str,
    issues: Vec<String>,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .map_err(|e| format!("stdin read failed: {e}"))?;
    let payload: Payload = if input.trim().is_empty() {
        Payload {
            roads: Some(vec![]),
            connectors: Some(vec![]),
        }
    } else {
        serde_json::from_str(&input).map_err(|e| format!("json parse failed: {e}"))?
    };
    let mut issues = Vec::new();
    for (i, road) in payload.roads.unwrap_or_default().into_iter().enumerate() {
        match road.get("geom").and_then(|v| v.as_array()) {
            Some(geom) if geom.len() >= 2 => {}
            _ => issues.push(format!("road[{i}] has invalid geometry")),
        }
        if road.get("name").is_none() {
            issues.push(format!("road[{i}] missing name"));
        }
    }
    for (i, conn) in payload.connectors.unwrap_or_default().into_iter().enumerate() {
        for side in ["a", "b"] {
            let ok = conn
                .get(side)
                .and_then(|v| v.as_array())
                .map(|v| v.len() == 3)
                .unwrap_or(false);
            if !ok {
                issues.push(format!("connector[{i}].{side} invalid node"));
            }
        }
    }
    let out = Output {
        engine: "rust-validator",
        issues,
    };
    let json = serde_json::to_string(&out).map_err(|e| format!("serialize failed: {e}"))?;
    println!("{json}");
    Ok(())
}
