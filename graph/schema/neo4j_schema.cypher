CREATE CONSTRAINT service_name_unique IF NOT EXISTS
FOR (s:Service) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT workload_uid_unique IF NOT EXISTS
FOR (w:Workload) REQUIRE w.uid IS UNIQUE;

CREATE CONSTRAINT owner_key_unique IF NOT EXISTS
FOR (o:Owner) REQUIRE o.key IS UNIQUE;

CREATE CONSTRAINT incident_id_unique IF NOT EXISTS
FOR (i:Incident) REQUIRE i.id IS UNIQUE;

CREATE INDEX service_environment_index IF NOT EXISTS
FOR (s:Service) ON (s.environment);

CREATE INDEX incident_timestamp_index IF NOT EXISTS
FOR (i:Incident) ON (i.timestamp);
