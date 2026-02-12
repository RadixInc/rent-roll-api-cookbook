# OpenAPI Specification

The file `rent-roll-api.yaml` is the OpenAPI 3.0 specification for the Radix Underwriting Rent Roll API.

## Endpoints Covered

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/external/v1/upload` | Upload rent roll files for processing |
| GET | `/api/external/v1/job/{batchId}/status` | Check batch processing status |

## How to Use

### View in Swagger UI

```bash
# Using Docker
docker run -p 8080:8080 -e SWAGGER_JSON=/spec/rent-roll-api.yaml -v $(pwd):/spec swaggerapi/swagger-ui

# Then open http://localhost:8080
```

### View with Redocly

```bash
npx @redocly/cli preview-docs rent-roll-api.yaml
```

### Import into Postman

1. Open Postman.
2. Click **Import** in the top left.
3. Drag `rent-roll-api.yaml` into the import window.
4. Postman will generate a collection from the spec.

### Import into Insomnia

1. Open Insomnia.
2. Click **Create** > **Import from File**.
3. Select `rent-roll-api.yaml`.

## Server

The spec points to the production endpoint:

```
https://connect.rediq.io
```


