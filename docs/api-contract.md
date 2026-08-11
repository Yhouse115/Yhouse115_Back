# API Contract

## Health Check

### `GET /health`

Returns backend runtime health.

Response:

```json
{
  "status": "ok",
  "service": "WhyHouse Backend",
  "environment": "local",
  "version": "0.1.0"
}
```

### `GET /api/v1/health`

Versioned alias for the same health response.

## Planned MVP Endpoints

The following endpoints are planned but not implemented in this setup phase.

- `GET /apartments`
- `GET /nearby-infrastructure`
- `GET /child-safety`
- `GET /routes`

Detailed request and response schemas should be added here when each endpoint is implemented.

