import { createClient } from "npm:@supabase/supabase-js@2";

function secret() {
  const value = Deno.env.get("SUPABASE_SECRET_KEY")?.trim() || Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")?.trim();
  if (!value) throw new Error("service key unavailable");
  return value;
}

const reply = (status: number, body: unknown) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
});

function ageHours(value: unknown) {
  const time = new Date(String(value ?? "")).getTime();
  return Number.isFinite(time) ? Math.max(0, (Date.now() - time) / 3600000) : null;
}

function activeSlateDate(value: unknown) {
  const time = new Date(`${String(value ?? "")}T18:00:00Z`).getTime();
  return Number.isFinite(time) && time >= Date.now() - 36 * 3600000 && time <= Date.now() + 4 * 86400000;
}

function cbbSeason() {
  return [10, 11, 0, 1, 2, 3].includes(new Date().getUTCMonth());
}

Deno.serve(async (req) => {
  if (req.method !== "GET") return reply(405, { error: "GET only" });
  try {
    const url = Deno.env.get("SUPABASE_URL");
    if (!url) throw new Error("url unavailable");
    const db = createClient(url, secret(), { auth: { persistSession: false, autoRefreshToken: false } });

    const [{ data: slate, error: slateError }, { data: snapshot, error: snapshotError }] = await Promise.all([
      db.from("cbb_slates").select("slate_date,model_version,revision,board_rows,metrics_json,published_at,updated_at").order("published_at", { ascending: false }).limit(1).maybeSingle(),
      db.from("cbb_market_snapshots").select("snapshot_time_utc,provider,market_type,book_count,created_at,updated_at").order("snapshot_time_utc", { ascending: false }).limit(1).maybeSingle(),
    ]);
    if (slateError || snapshotError) throw slateError || snapshotError;

    const operatingState = cbbSeason() ? "active" : "offseason";
    const lastMarket = snapshot?.snapshot_time_utc ?? null;
    const marketAge = ageHours(lastMarket);
    const marketExpected = operatingState === "active" && activeSlateDate(slate?.slate_date);
    const marketRows = snapshot ? 1 : 0;
    const oddsPopulating = marketExpected ? Boolean(lastMarket && marketAge !== null && marketAge <= 4 && marketRows > 0) : null;
    const boardRows = Number(slate?.board_rows ?? 0);
    const modelOk = slate ? boardRows > 0 : operatingState === "offseason" ? null : false;

    const incidents: string[] = [];
    if (operatingState === "active" && slate && boardRows <= 0) incidents.push("published board has zero rows");
    if (marketExpected && oddsPopulating === false) incidents.push("market data is stale or absent for the active slate");

    const workflowStatus = operatingState === "offseason" ? "idle" : incidents.length ? "incident" : "healthy";
    return reply(200, {
      sport: "cbb",
      checked_at: new Date().toISOString(),
      operating_state: operatingState,
      market_expected: marketExpected,
      last_owls_refresh: lastMarket,
      odds_populating: oddsPopulating,
      latest_market_status: lastMarket ? "observed" : "unavailable",
      market_rows: marketRows,
      last_model_run: slate?.published_at ?? null,
      latest_model_status: slate ? "published" : null,
      latest_model_stage: null,
      model_output_count: boardRows,
      model_outputs_ok: modelOk,
      latest_slate: slate ?? null,
      workflow_status: workflowStatus,
      workflow_summary: incidents.join(", ") || (operatingState === "offseason" ? "College basketball is out of season; fresh model and market data are not expected." : null),
      anomaly_status: incidents.length ? "incident" : "clear",
      anomaly_summary: incidents.length ? incidents.join(", ") : null,
      detail: {
        market_age_hours: marketAge,
        snapshot_present: Boolean(snapshot),
        market_source: "cbb_market_snapshots",
      },
    });
  } catch (error) {
    return reply(500, {
      sport: "cbb",
      checked_at: new Date().toISOString(),
      operating_state: cbbSeason() ? "active" : "offseason",
      workflow_status: "incident",
      error: String((error as any)?.message ?? error).slice(0, 400),
    });
  }
});
