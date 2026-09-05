import express from "express";
import cors from "cors";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { Octokit } from "@octokit/rest";

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const octokit = new Octokit({ auth: process.env.GITHUB_PERSONAL_ACCESS_TOKEN });

const handleAuthorize = (req, res) => {
  const { redirect_uri, state } = req.query;
  if (redirect_uri) {
    return res.redirect(`${redirect_uri}?code=auth_code_ok&state=${state || ""}`);
  }
  res.send("Autorización completa");
};

app.get(["/authorize", "/oauth/authorize"], handleAuthorize);

const handleToken = (req, res) => {
  res.json({
    access_token: "token_mcp_ok",
    token_type: "Bearer",
    expires_in: 3600
  });
};

app.post(["/token", "/oauth/token"], handleToken);

// Mapa para gestionar las sesiones activas de SSE
const transports = {};

app.get("/sse", async (req, res) => {
  const transport = new SSEServerTransport("/messages", res);
  transports[transport.sessionId] = transport;

  res.on("close", () => {
    delete transports[transport.sessionId];
  });

  const server = new Server(
    { name: "github-mcp-server", version: "1.0.0" },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler("tools/list", async () => ({
    tools: [
      {
        name: "list_repositories",
        description: "Lista los repositorios de GitHub del usuario",
        inputSchema: { type: "object", properties: {} }
      }
    ]
  }));

  server.setRequestHandler("tools/call", async (request) => {
    if (request.params.name === "list_repositories") {
      try {
        const response = await octokit.repos.listForAuthenticatedUser();
        const repoNames = response.data.map(r => r.name);
        return {
          content: [{ type: "text", text: JSON.stringify(repoNames, null, 2) }]
        };
      } catch (error) {
        throw new Error(error.message);
      }
    }
    throw new Error("Herramienta no encontrada");
  });

  await server.connect(transport);
});

app.post("/messages", async (req, res) => {
  const sessionId = req.query.sessionId;
  const transport = transports[sessionId];
  if (transport) {
    await transport.handlePostMessage(req, res);
  } else {
    res.status(400).send("No active transport session for sessionId: " + sessionId);
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Servidor MCP corriendo en el puerto ${PORT}`);
});
