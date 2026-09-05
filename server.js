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
  console.log("-> [AUTH] Solicitud de autorización recibida");
  const { redirect_uri, state } = req.query;
  if (redirect_uri) {
    return res.redirect(`${redirect_uri}?code=auth_code_ok&state=${state || ""}`);
  }
  res.send("Autorización completa");
};

app.get(["/authorize", "/oauth/authorize"], handleAuthorize);

const handleToken = (req, res) => {
  console.log("-> [TOKEN] Solicitud de intercambio de token OAuth recibida");
  res.json({
    access_token: "token_mcp_ok",
    token_type: "Bearer",
    expires_in: 3600
  });
};

app.post(["/token", "/oauth/token"], handleToken);

const transports = {};

app.get("/sse", async (req, res) => {
  console.log("-> [SSE] Nueva conexión SSE iniciada por el cliente");
  const transport = new SSEServerTransport("/messages", res);
  transports[transport.sessionId] = transport;

  res.on("close", () => {
    console.log(`-> [SSE] Conexión cerrada para sesión: ${transport.sessionId}`);
    delete transports[transport.sessionId];
  });

  const server = new Server(
    { name: "github-mcp-server", version: "1.0.0" },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler("tools/list", async () => {
    console.log("-> [MCP] Herramientas solicitadas (tools/list)");
    return {
      tools: [
        {
          name: "list_repositories",
          description: "Lista los repositorios de GitHub del usuario",
          inputSchema: { type: "object", properties: {} }
        }
      ]
    };
  });

  server.setRequestHandler("tools/call", async (request) => {
    console.log(`-> [MCP] Ejecutando herramienta: ${request.params.name}`);
    if (request.params.name === "list_repositories") {
      try {
        const response = await octokit.repos.listForAuthenticatedUser();
        const repoNames = response.data.map(r => r.name);
        return {
          content: [{ type: "text", text: JSON.stringify(repoNames, null, 2) }]
        };
      } catch (error) {
        console.error("-> [ERROR] GitHub API Error:", error.message);
        throw new Error(error.message);
      }
    }
    throw new Error("Herramienta no encontrada");
  });

  await server.connect(transport);
});

app.post("/messages", async (req, res) => {
  const sessionId = req.query.sessionId;
  console.log(`-> [MESSAGES] Mensaje POST recibido para sessionId: ${sessionId}`);
  const transport = transports[sessionId];
  if (transport) {
    await transport.handlePostMessage(req, res);
  } else {
    console.warn(`-> [WARN] Sesión no encontrada o expirada para sessionId: ${sessionId}`);
    res.status(400).send("No active transport session for sessionId: " + sessionId);
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Servidor MCP corriendo en el puerto ${PORT}`);
});
