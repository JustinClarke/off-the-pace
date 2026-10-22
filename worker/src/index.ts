import { handle, type Env } from "./handler";
import { Ledger_DO, StubLedger } from "./ledger";

export { Ledger_DO as Ledger };

export default {
  fetch(req: Request, env: Env) {
    const stub = env.LEDGER.get(env.LEDGER.idFromName("global"));
    return handle(req, env, { ledger: new StubLedger(stub), fetch, now: () => new Date(), log: (m) => console.error(m) });
  },
};
