---
name: api-design
description: Use when adding or changing an HTTP API or endpoint, or anything the frontend calls. Conventions for routes, validation and errors, and the API.md contract frontren builds against.
---

# API design

1. Write the contract first, in `API.md` at the project root. For each endpoint: method and path, query parameters and request body with types, the response body on success, and every error status with its body. frontren builds against this file, so change it in the same change as the code.
2. Resources are nouns and methods are verbs: `GET /api/tasks`, `POST /api/tasks`, `PATCH /api/tasks/{id}`, `DELETE /api/tasks/{id}`. Keep every route under one prefix such as `/api`.
3. Validate every input at the boundary (types, required fields, lengths, ranges) and answer `400` with `{"error": "<what is wrong, in words the user could act on>"}`. Never let a stack trace reach the response.
4. Status codes: `200`/`201` on success, `204` with no body, `400` bad input, `401` not signed in, `403` not allowed, `404` not found, `409` conflict, `500` only for real bugs.
5. JSON in and out in UTF-8, times as ISO 8601 in UTC, ids as strings.
6. A list that can grow is paginated (`limit` and a cursor or `offset`) and has a stable order.
7. In development, allow CORS only for the frontend's origin; never `*` together with credentials.
8. Secrets and settings come from environment variables, listed in `.env.example` and the README, never committed.
9. Test each endpoint at least for success, a validation error and a missing resource.
