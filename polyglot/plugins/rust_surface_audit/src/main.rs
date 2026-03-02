use serde::Deserialize;
use serde::Serialize;
use std::collections::BTreeMap;
use std::io::{self, Read};

#[derive(Deserialize)]
struct Road {
    surface: Option<String>,
    max_weight: Option<f64>,
}

#[derive(Deserialize)]
struct Payload {
    roads: Option<Vec<Road>>,
}

#[derive(Serialize)]
struct Output {
    plugin_kind: &'static str,
    surface_counts: BTreeMap<String, usize>,
    weight_limited: usize,
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
        Payload { roads: Some(vec![]) }
    } else {
        serde_json::from_str(&input).map_err(|e| format!("json parse failed: {e}"))?
    };
    let mut surface_counts = BTreeMap::new();
    let mut weight_limited = 0usize;
    for road in payload.roads.unwrap_or_default() {
        let surface = road.surface.unwrap_or_else(|| "unknown".to_string());
        *surface_counts.entry(surface).or_insert(0) += 1;
        if road.max_weight.unwrap_or(0.0) > 0.0 {
            weight_limited += 1;
        }
    }
    let out = Output {
        plugin_kind: "surface_audit",
        surface_counts,
        weight_limited,
    };
    let json = serde_json::to_string(&out).map_err(|e| format!("serialize failed: {e}"))?;
    println!("{json}");
    Ok(())
}
