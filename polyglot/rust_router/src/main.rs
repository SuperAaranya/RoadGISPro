use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap};
use std::io::{self, Read};

#[derive(Deserialize, Clone)]
struct Node([f64; 3]);

#[derive(Deserialize)]
struct EdgeIn {
    to: Node,
    weight: f64,
}

#[derive(Deserialize)]
struct NodeEdgesIn {
    node: Node,
    edges: Vec<EdgeIn>,
}

#[derive(Deserialize)]
struct Request {
    start: Node,
    end: Node,
    graph: Vec<NodeEdgesIn>,
}

#[derive(Serialize)]
struct Response {
    path: Vec<[f64; 3]>,
    travel_hours: f64,
}

#[derive(Copy, Clone, PartialEq)]
struct State {
    cost: f64,
    node_idx: usize,
}

impl Eq for State {}

impl Ord for State {
    fn cmp(&self, other: &Self) -> Ordering {
        other
            .cost
            .partial_cmp(&self.cost)
            .unwrap_or(Ordering::Equal)
    }
}

impl PartialOrd for State {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

fn node_to_arr(node: &Node) -> [f64; 3] {
    [node.0[0], node.0[1], node.0[2]]
}

fn node_key(node: &Node) -> String {
    format!("{:.9}|{:.9}|{:.0}", node.0[0], node.0[1], node.0[2])
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
    let req: Request =
        serde_json::from_str(&input).map_err(|e| format!("request parse failed: {e}"))?;

    let mut index_of: HashMap<String, usize> = HashMap::new();
    let mut nodes: Vec<Node> = Vec::new();
    for entry in &req.graph {
        let k = node_key(&entry.node);
        if !index_of.contains_key(&k) {
            let idx = nodes.len();
            nodes.push(entry.node.clone());
            index_of.insert(k, idx);
        }
        for e in &entry.edges {
            let k = node_key(&e.to);
            if !index_of.contains_key(&k) {
                let idx = nodes.len();
                nodes.push(e.to.clone());
                index_of.insert(k, idx);
            }
        }
    }

    let start_idx = *index_of
        .get(&node_key(&req.start))
        .ok_or_else(|| "start not in graph".to_string())?;
    let end_idx = *index_of
        .get(&node_key(&req.end))
        .ok_or_else(|| "end not in graph".to_string())?;

    let mut adj: Vec<Vec<(usize, f64)>> = vec![Vec::new(); nodes.len()];
    for entry in req.graph {
        let from_idx = *index_of
            .get(&node_key(&entry.node))
            .ok_or_else(|| "graph node indexing failure".to_string())?;
        for e in entry.edges {
            let to_idx = *index_of
                .get(&node_key(&e.to))
                .ok_or_else(|| "edge node indexing failure".to_string())?;
            adj[from_idx].push((to_idx, e.weight));
        }
    }

    let mut dist = vec![f64::INFINITY; nodes.len()];
    let mut prev: Vec<Option<usize>> = vec![None; nodes.len()];
    let mut heap = BinaryHeap::new();
    dist[start_idx] = 0.0;
    heap.push(State {
        cost: 0.0,
        node_idx: start_idx,
    });

    while let Some(State { cost, node_idx }) = heap.pop() {
        if cost > dist[node_idx] {
            continue;
        }
        if node_idx == end_idx {
            break;
        }
        for &(next_idx, weight) in &adj[node_idx] {
            let next_cost = cost + weight;
            if next_cost < dist[next_idx] {
                dist[next_idx] = next_cost;
                prev[next_idx] = Some(node_idx);
                heap.push(State {
                    cost: next_cost,
                    node_idx: next_idx,
                });
            }
        }
    }

    if !dist[end_idx].is_finite() {
        return Err("no path found".to_string());
    }

    let mut path_idx = Vec::new();
    let mut cur = end_idx;
    path_idx.push(cur);
    while cur != start_idx {
        cur = prev[cur].ok_or_else(|| "path reconstruction failed".to_string())?;
        path_idx.push(cur);
    }
    path_idx.reverse();

    let path = path_idx.iter().map(|&i| node_to_arr(&nodes[i])).collect();
    let response = Response {
        path,
        travel_hours: dist[end_idx],
    };
    let json = serde_json::to_string(&response).map_err(|e| format!("response serialize failed: {e}"))?;
    println!("{json}");
    Ok(())
}
