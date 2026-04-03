import { setTimeout as sleep } from "node:timers/promises";
import { spawn, type ChildProcess } from "node:child_process";

import WebSocket from "ws";

import type { ModelListResponse } from "./generated/v2/ModelListResponse.js";
import type { Model } from "./generated/v2/Model.js";

type JsonRpcEnvelope = {
  id?: string;
  result?: unknown;
  error?: {
    message?: string;
  };
};

export class AppServerClient {
  private socket: WebSocket | null = null;
  private nextRequestId = 1;
  private readonly pending = new Map<
    string,
    {
      resolve: (value: unknown) => void;
      reject: (error: Error) => void;
    }
  >();

  constructor(private readonly url: string) {}

  async connect() {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      return;
    }

    this.socket = await new Promise<WebSocket>((resolve, reject) => {
      const socket = new WebSocket(this.url);
      socket.once("open", () => resolve(socket));
      socket.once("error", (error) => reject(error));
    });

    this.socket.on("message", (payload) => {
      const message = JSON.parse(payload.toString()) as JsonRpcEnvelope;
      if (!message.id) {
        return;
      }

      const handler = this.pending.get(message.id);
      if (!handler) {
        return;
      }

      this.pending.delete(message.id);
      if (message.error?.message) {
        handler.reject(new Error(message.error.message));
        return;
      }

      handler.resolve(message.result);
    });
  }

  async initialize() {
    await this.connect();
    await this.request("initialize", {
      clientInfo: {
        name: "reasonforge",
        version: "0.1.0"
      }
    });
  }

  async request<T>(method: string, params: unknown): Promise<T> {
    await this.connect();
    const id = String(this.nextRequestId++);

    const response = await new Promise<unknown>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.socket?.send(JSON.stringify({ method, id, params }));
    });

    return response as T;
  }

  async listModels() {
    const response = await this.request<ModelListResponse>("model/list", {
      includeHidden: false
    });
    return response.data as Model[];
  }

  async close() {
    if (!this.socket) {
      return;
    }

    await new Promise<void>((resolve) => {
      this.socket?.once("close", () => resolve());
      this.socket?.close();
    });
  }
}

export type LocalAppServerHandle = {
  client: AppServerClient;
  child: ChildProcess;
  url: string;
  close: () => Promise<void>;
};

export async function startLocalAppServer(url: string) {
  const child = spawn("codex", ["app-server", "--listen", url], {
    stdio: ["ignore", "pipe", "pipe"]
  });

  await sleep(1_000);

  const client = new AppServerClient(url);
  await client.initialize();

  return {
    client,
    child,
    url,
    close: async () => {
      await client.close();
      child.kill("SIGTERM");
    }
  } satisfies LocalAppServerHandle;
}
