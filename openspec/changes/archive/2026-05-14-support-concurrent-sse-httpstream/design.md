## Context

The service uses the Python MCP SDK `FastMCP` to define one shared tool set and currently configures both HTTP paths on the server object: streamable HTTP at `/mcp` and SSE at `/sse`. Startup still calls `mcp.run(transport=settings.transport)`, so the running process only activates the selected transport.

The current configuration also includes `transport` / `MCP_TRANSPORT`, which makes transport availability a deployment-time choice. The desired behavior is a single service instance that lets streamable HTTP clients and SSE clients connect concurrently.

## Goals / Non-Goals

**Goals:**

- Expose streamable HTTP and SSE from the same running service process.
- Keep `/mcp` and `/sse` as the stable transport endpoint paths.
- Ensure both transports use the same registered MCP tools and the same runtime settings.
- Remove transport selection from normal runtime behavior while keeping configuration compatibility where practical.
- Update docs and checks so users no longer start separate transport-specific modes.

**Non-Goals:**

- Add new MCP tools or change tool request/response schemas.
- Add new authentication, authorization, session persistence, or proxy behavior.
- Change host, port, CDP, timeout, concurrency, search, or result-limit configuration semantics except where they mention transport selection.

## Decisions

### Serve both transport ASGI apps from one process

Build startup around a single ASGI application that mounts both MCP transport applications, then run that app once on the configured host and port. This keeps one process and one port while allowing clients to choose `/mcp` or `/sse` per connection.

Alternative considered: starting two separate server processes or two independent listeners. That would satisfy availability but introduces duplicate lifecycle management, possible port conflicts, and unclear ownership of shared settings.

### Keep one FastMCP instance as the source of tool registration

Continue to register tools once through `create_mcp(settings)`. The two transport endpoints should be derived from that same MCP server instance so `fetch`, `batch-fetch`, `search`, and `search_img` stay consistent across transports.

Alternative considered: create separate FastMCP instances per transport. That risks tool drift and duplicated browser/search service state.

### Treat transport configuration as deprecated compatibility input

The implementation should stop using `settings.transport` to decide which transport is served. For compatibility, existing `transport` config and `MCP_TRANSPORT` environment values can remain accepted initially, but they should not disable either endpoint. Documentation should describe them as no longer needed or remove them from examples.

Alternative considered: reject `transport` / `MCP_TRANSPORT`. That is cleaner long-term but turns a deployment convenience change into an avoidable configuration breaking change.

### Verify endpoint availability at the transport boundary

Tests should assert that service construction or startup exposes both configured endpoint paths. Manual checks should include connecting one client to `/mcp` and another to `/sse` against the same running process.

Alternative considered: rely only on SDK behavior. Because the current regression is specifically at startup transport selection, explicit coverage around both endpoints is worthwhile.

## Risks / Trade-offs

- MCP SDK APIs for composing both transport apps may differ by version -> inspect the installed SDK surface and use documented/public FastMCP methods where available.
- Sharing one MCP server instance across two transports may expose lifecycle assumptions in the SDK -> add a smoke test or manual check that both endpoints can initialize independently in one process.
- Keeping deprecated transport config may confuse users -> remove it from examples and note that both transports are always exposed.
- Running both endpoints increases exposed HTTP surface area -> document both paths clearly and keep host binding behavior unchanged so local-only defaults remain local-only.

## Migration Plan

1. Update service startup to serve both transports on the configured host and port.
2. Keep existing `/mcp` and `/sse` endpoint paths available.
3. Leave `transport` / `MCP_TRANSPORT` accepted during the transition but ignore it for endpoint selection.
4. Update README, config example, Docker environment defaults, and manual checks to describe concurrent transport availability.
5. Rollback by restoring single-transport `mcp.run(transport=settings.transport)` startup if a blocking SDK issue is found.

## Open Questions

- Should `transport` / `MCP_TRANSPORT` be removed in a later cleanup change after users have had a compatibility window?
