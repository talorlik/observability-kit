# Troubleshooting

## Schema Failures

- Confirm `observability` block exists in values.
- Confirm required keys are present and non-empty.
- Confirm `subscriptionMode` is one of allowed enum values.

## Policy Rejections

- Check workload labels include `service.name`.
- Check workload labels include `deployment.environment`.
- Check workload labels include `service.owner`.

## Runtime Issues

- Verify collector agent is healthy.
- Verify scrape opt-in labels or annotations match expected keys.
- Verify logs, metrics, and traces arrive in expected index families.
