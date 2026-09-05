import express from "express";
import cors from "cors";
import { Octokit } from "@octokit/rest";

const app = express();
app.use(cors());
app.use(express.json());

const octokit = new Octokit({ auth: process.env.GITHUB_PERSONAL_ACCESS_TOKEN });

app.get("/sse", (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();

  res.write(`event: endpoint\ndata: /messages\n\n`);
});

app.post("/messages", async (req, res) => {
  const message = req.body;
  
  if (message.method === "initialize") {
    return res.json({
      jsonrpc: "2.0",
      id: message.id,
      result: {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "github-mcp-server", version: "1.0.0" }
      }
    });
  }

  if (message.method === "tools/list") {
    return res.json({
      jsonrpc: "2.0",
      id: message.id,
      result: {
        tools: [
          {
            name: "list_repositories",
            description: "Lista los repositorios de GitHub del usuario",
            inputSchema: { type: "object", properties: {} }
          }
        ]
      }
    });
  }

  if (message.method === "tools/call" && message.params?.name === "list_repositories") {
    try {
      const response = await octokit.repos.listForAuthenticatedUser();
      const repoNames = response.data.map(r => r.name);
      return res.json({
        jsonrpc: "2.0",
        id: message.id,
        result: {
          content: [{ type: "text", text: JSON.stringify(repoNames, null, 2) }]
        }
      });
    } catch (error) {
      return res.json({
        jsonrpc: "2.0",
        id: message.id,
        error: { code: -32603, message: error.message }
      });
    }
  }

  return res.status(404).json({ jsonrpc: "2.0", id: message.id, error: { code: -32601, message: "Method not found" } });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Servidor MCP corriendo en el puerto ${PORT}`);
});
