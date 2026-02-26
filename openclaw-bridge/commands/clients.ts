import { runShell } from "../runner";

export function registerClients(api: { registerCommand: (c: unknown) => void }) {
  api.registerCommand({
    name: "clients",
    description: "List configured clients. Usage: /clients",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      try {
        const out = runShell(
          `for f in /root/operator/factory/clients/*.json; do jq -r '"- " + .id + " (" + .name + ") topics=" + (.topics|join(","))' "$f" 2>/dev/null; done`,
          10_000
        );
        return { text: out ? `Configured clients:\n\n${out}` : "No clients configured." };
      } catch (e: unknown) {
        return { text: `Failed: ${(e as Error).message}` };
      }
    },
  });
}
