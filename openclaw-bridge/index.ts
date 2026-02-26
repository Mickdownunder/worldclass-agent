import { registerJobs } from "./commands/jobs";
import { registerHealth } from "./commands/health";
import { registerQueue } from "./commands/queue";
import { registerBrain } from "./commands/brain";
import { registerClients } from "./commands/clients";
import { registerResearch } from "./commands/research";

export default function (api: { registerCommand: (c: unknown) => void }) {
  registerJobs(api);
  registerHealth(api);
  registerQueue(api);
  registerBrain(api);
  registerClients(api);
  registerResearch(api);
}
