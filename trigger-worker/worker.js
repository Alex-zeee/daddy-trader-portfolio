// Daddy Trader - signal robot ki ghari (Cloudflare Worker)
//
// GitHub ka apna schedule kabhi kabhi ghanton late chalta hai.
// Ye worker Cloudflare ki ghari (cron: 1,16,31,46 * * * *) se har 15 minute bilkul waqt par
// GitHub ko kehta hai "signal robot abhi chalao" (workflow_dispatch). Is tarah bulaya gaya robot foran chalta hai.
// Secret: GH_TOKEN = GitHub fine-grained token (sirf daddy-trader-portfolio repo, Actions: Read and write)

const REPO = "Alex-zeee/daddy-trader-portfolio";
const WORKFLOWS = ["signals.yml"];

async function dispatch(env, wf) {
  const url = "https://api.github.com/repos/" + REPO + "/actions/workflows/" + wf + "/dispatches";
  const r = await fetch(url, {
    method: "POST",
    headers: {
      authorization: "Bearer " + env.GH_TOKEN,
      accept: "application/vnd.github+json",
      "content-type": "application/json",
      "user-agent": "daddytrader-trigger",
      "x-github-api-version": "2022-11-28",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  const note = r.ok ? "" : " " + (await r.text()).slice(0, 200);
  return wf + " " + r.status + note;
}

export default {
  async scheduled(event, env, ctx) {
    if (!env.GH_TOKEN) {
      console.log("GH_TOKEN secret nahi mila");
      return;
    }
    const res = await Promise.all(WORKFLOWS.map((wf) => dispatch(env, wf)));
    console.log(res.join(" | "));
  },
  async fetch(req, env) {
    return new Response("Daddy Trader signal ghari chal rahi hai", {
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  },
};
