package observability.ai.boundary

default allow = true

deny[msg] {
  input.path.from == "ai_components"
  blocked_target(input.path.to)
  msg := sprintf(
    "direct datastore access denied: %s -> %s",
    [input.path.from, input.path.to],
  )
}

deny[msg] {
  input.path.from == "khook"
  input.path.to == "datastore_native"
  msg := "khook cannot access datastore native protocols directly"
}

blocked_target(target) {
  target == "opensearch_native"
}

blocked_target(target) {
  target == "neo4j_native"
}

blocked_target(target) {
  target == "sql_native"
}
