import express from "express";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { Octokit } from "@octokit/rest";

const app = express();
const octokit = new Octokit({ auth: process.env.GITHUB_PERSONAL_ACCESS_TOKEN });

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
    const response = await octokit.repos.listForAuthenticatedUser();
    return {
      content: [{ type: "text", text: JSON.stringify(response.data.map(r => r.name)) }]
    };
  }
  throw new Error("Herramienta no encontrada");
});

let transport;

app.get("/sse", async (req, res) => {
  transport = new SSEServerTransport("/messages", res);
  await server.connect(transport);
});

app.post("/messages", async (req, res) => {
  if (transport) {
    await transport.handlePostMessage(req, res);
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Servidor MCP corriendo en el puerto ${PORT}`);
});
