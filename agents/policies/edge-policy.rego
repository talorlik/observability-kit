package observability.ai.communication

default allow = false

allow {
  input.from == "ceo"
  input.to == "manager"
}

allow {
  input.from == "manager"
  input.to == "specialist"
}

allow {
  input.from == "ceo"
  input.to == "specialist"
}

deny_reason := "specialist-to-specialist communication is not allowed" {
  input.from == "specialist"
  input.to == "specialist"
}
