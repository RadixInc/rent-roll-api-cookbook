## Model Context Protocol (MCP) Servers

This folder contains Model Context Protocol (MCP) servers for interacting with the Radix Rent Roll Processing API from AI assistants and automation tools.

These MCP servers allow tools like Claude Desktop, agent frameworks, and custom automation workflows to upload rent rolls, manage deals, monitor processing, and retrieve structured outputs.

Both MCP servers now expose the API's `Deals` CRUD endpoints plus upload support for optional `dealId`, so models can create or look up a deal and attach a batch to it. One upload request can carry only one `dealId`, which means every file in that batch maps to the same deal.

---

## Why Two MCP Versions?

Different environments have different needs.

* Some integrations require a **clean API surface** for automation and server-side workflows.
* Others benefit from a **fully orchestrated workflow** that handles downloading, extracting, and previewing processed data for AI assistants.

To support both use cases, we provide:

### 🔹 Core MCP

A lightweight MCP server that exposes a direct interface to the Rent Roll API.

**Best for:**

* automation pipelines
* server-side agents
* backend integrations
* CI/CD workflows
* custom tooling

👉 See: [`core-mcp/`](./core-mcp)

---

### 🔹 Agent MCP

An enhanced MCP server designed for AI assistants and local agent environments.

It adds workflow orchestration and data extraction to make processed results immediately usable.

**Adds capabilities such as:**

* end-to-end workflow orchestration
* ZIP download & extraction
* structured CSV previews for AI analysis
* temporary artifact handling
* filesystem-friendly operation

**Best for:**

* Claude Desktop
* local AI assistants
* analyst workflows
* agent frameworks with filesystem access

👉 See: [`agent-mcp/`](./agent-mcp)

---

## Which One Should I Use?

| Use Case                         | Recommended MCP |
| -------------------------------- | --------------- |
| Automation / backend integration | Core MCP        |
| AI assistant workflows           | Agent MCP       |
| Claude Desktop                   | Agent MCP       |
| Custom scripting                 | Core MCP        |
| Local analysis & preview         | Agent MCP       |

---

## Requirements

* Python 3.10+
* Valid Radix API credentials

---

## Security Note

Both MCP servers run locally and require a valid API key.
Never share API keys publicly.

---

## Future Extensions

These MCP servers are designed to evolve alongside the Rent Roll API. Future enhancements may include:

* additional document processing workflows
* expanded output formats
* advanced agent integrations

---

## Support

If you encounter issues, verify:

* dependencies are installed
* environment variables are set correctly
* MCP configuration paths are correct

---
