import { afterEach, describe, expect, it } from "vitest";
import { WebSocketServer } from "ws";

import { AppServerClient } from "../src/index";

const servers: WebSocketServer[] = [];

describe("AppServerClient", () => {
  afterEach(() => {
    for (const server of servers.splice(0)) {
      server.close();
    }
  });

  it("initializes and requests the model list over websocket JSON-RPC", async () => {
    const server = new WebSocketServer({ port: 0 });
    servers.push(server);
    await new Promise((resolve) => server.once("listening", resolve));
    const address = server.address();
    const port = typeof address === "object" && address ? address.port : 8897;

    server.on("connection", (socket) => {
      socket.on("message", (payload) => {
        const message = JSON.parse(payload.toString()) as {
          id: string;
          method: string;
        };

        if (message.method === "initialize") {
          socket.send(
            JSON.stringify({
              id: message.id,
              result: { codexHome: "/tmp/.codex" }
            })
          );
          return;
        }

        if (message.method === "model/list") {
          socket.send(
            JSON.stringify({
              id: message.id,
              result: {
                data: [
                  {
                    id: "gpt-5.4",
                    displayName: "gpt-5.4",
                    hidden: false,
                    isDefault: true
                  }
                ],
                nextCursor: null
              }
            })
          );
        }
      });
    });

    const client = new AppServerClient(`ws://127.0.0.1:${port}`);

    await client.initialize();
    const models = await client.listModels();

    expect(models).toHaveLength(1);
    expect(models[0]?.id).toBe("gpt-5.4");
    await client.close();
  });
});
