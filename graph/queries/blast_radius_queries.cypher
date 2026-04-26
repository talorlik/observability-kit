// Blast radius from an impacted service.
MATCH path = (root:Service {name: $service_name})<-[:DEPENDS_ON*1..4]-(affected:Service)
RETURN affected.name AS affected_service, length(path) AS hop_distance
ORDER BY hop_distance ASC, affected_service ASC
LIMIT 200;

// Open incidents connected to impacted services.
MATCH (i:Incident)-[:IMPACTS]->(svc:Service {name: $service_name})
RETURN i.id AS incident_id, i.severity AS severity, i.timestamp AS occurred_at
ORDER BY occurred_at DESC
LIMIT 50;
