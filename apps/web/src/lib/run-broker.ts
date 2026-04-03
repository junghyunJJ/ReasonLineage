import { EventEmitter } from "node:events";

import type { PublicRunEvent } from "./types";

type BrokerShape = {
  broker?: EventEmitter;
};

const globalBroker = globalThis as typeof globalThis & BrokerShape;

function getBroker() {
  if (!globalBroker.broker) {
    globalBroker.broker = new EventEmitter();
  }

  return globalBroker.broker;
}

export function publishRunEvent(runId: string, event: PublicRunEvent) {
  getBroker().emit(runId, event);
}

export function subscribeToRun(
  runId: string,
  listener: (event: PublicRunEvent) => void
) {
  const broker = getBroker();
  broker.on(runId, listener);

  return () => {
    broker.off(runId, listener);
  };
}
