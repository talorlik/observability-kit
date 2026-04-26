// Upstream dependencies for a service.
MATCH path = (src:Service {name: $service_name})-[:DEPENDS_ON*1..3]->(dep:Service)
RETURN path
LIMIT 100;

// Ownership chain for a service.
MATCH (svc:Service {name: $service_name})-[:OWNED_BY]->(owner:Owner)
RETURN svc.name AS service_name, owner.key AS owner_key, owner.team AS owner_team;
