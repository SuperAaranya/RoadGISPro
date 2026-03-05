#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"

raw = STDIN.read
payload = raw.strip.empty? ? {} : JSON.parse(raw)
roads = payload["roads"].is_a?(Array) ? payload["roads"] : []
connectors = payload["connectors"].is_a?(Array) ? payload["connectors"] : []

total_len = 0.0
total_speed = 0.0
total_lanes = 0.0
oneway_count = 0

roads.each do |road|
  next unless road.is_a?(Hash)

  total_speed += road.fetch("speed", 0).to_f
  total_lanes += road.fetch("lanes", 0).to_f
  oneway_count += 1 if road["oneway"]
  geom = road["geom"]
  next unless geom.is_a?(Array)

  geom.each_cons(2) do |a, b|
    next unless a.is_a?(Array) && b.is_a?(Array) && a.length >= 2 && b.length >= 2

    ax = a[0].to_f
    ay = a[1].to_f
    bx = b[0].to_f
    by = b[1].to_f
    total_len += Math.hypot(bx - ax, by - ay)
  end
end

road_count = roads.length
result = {
  engine: "ruby",
  road_count: road_count,
  connector_count: connectors.length,
  total_length_km: total_len / 1000.0,
  average_speed_limit: road_count.zero? ? 0.0 : (total_speed / road_count),
  average_lanes: road_count.zero? ? 0.0 : (total_lanes / road_count),
  oneway_share: road_count.zero? ? 0.0 : (oneway_count.to_f / road_count)
}

puts JSON.generate(result)
