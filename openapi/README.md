# OpenAPI Specification

The file `rent-roll-api.yaml` is the OpenAPI 3.0 specification for the Radix Underwriting Rent Roll API.

## Endpoints Covered

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/external/v1/upload` | Upload rent roll files for processing, optionally attaching the whole batch to a deal with `dealId` |
| GET | `/api/external/v1/job/{batchId}/status` | Check batch processing status |
| POST | `/api/external/v1/deals` | Create a deal and receive its `counterId` for later uploads |
| GET | `/api/external/v1/deals` | List deals for the authenticated account |
| GET | `/api/external/v1/deals/{counterId}` | Retrieve one deal by counter ID |
| PUT | `/api/external/v1/deals/{counterId}` | Update an existing deal |
| DELETE | `/api/external/v1/deals/{counterId}` | Soft-delete a deal |

## Upload-To-Deal Behavior

The upload request now supports an optional `dealId` field. Pass the `counterId` returned by the `Deals` endpoints when you want the extracted rent roll data from that batch attached to a specific deal in redIQ.

Only one `dealId` is accepted per upload request. If you are automating a folder full of rent rolls for multiple deals, group files by destination deal and send separate upload requests instead of a single mixed batch.

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


