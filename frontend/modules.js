"use strict";

function displayPairs(obj, prefix = "") {
  if (!obj || !Object.keys(obj).length) return '<div class="empty">No values recorded.</div>';
  return table(["Measure", "Value"], Object.entries(obj).map(([k,v]) => [
    prefix + k.replaceAll("_"," "), typeof v === "number" ? num(v, 2) : JSON.stringify(v)
  ]));
}
function readOnlyObject(obj, headline) {
  return panel(json(obj), headline);
}
function insightList(recommendations) {
  if (!recommendations.length) return '<div class="empty">No evidence-based review triggers. Set goals and add complete positions to improve analysis.</div>';
  return recommendations.map((a) =>
    '<div class="alert ' + (a.priority === "HIGH" ? "critical" : "") + '"><span class="symbol">◆</span><div><strong>' +
    esc(a.action) + '</strong><small>' + esc(a.why) + "</small></div></div>"
  ).join("");
}

async function renderCommandCenter() {
  const [portfolio, brief, health, goal, quality] = await Promise.all([
    api("/portfolio"), api("/analyst/brief"), api("/health-score"), api("/goals"), api("/quality"),
  ]);
  const issue = portfolio.data_issues.length;
  const html =
    '<div class="hero"><div><span class="eyebrow">THE WEALTH INTELLIGENCE DESK</span>' +
    '<h2>Build wealth with evidence, not guesswork.</h2>' +
    '<p>One integrated view of assets, liquidity, goals, risk and investment decisions. Every number has an explicit source or assumption.</p></div>' +
    '<button class="primary" data-route="allocation">Explore capital allocation →</button></div>' +
    '<div class="kpi-grid">' +
    metric("Net worth", money(portfolio.net_worth_ngn), "Valued assets less liabilities") +
    metric("Assets", money(portfolio.assets_ngn), "Excludes any unpriced investments") +
    metric("Liabilities", money(portfolio.liabilities_ngn), "Liabilities translated to NGN") +
    metric("Wealth health", health.score === null ? "Incomplete" : pct(health.score, 0),
      "Heuristic score • not a credit rating") + "</div>" +
    section("Your financial position", "Live calculations from your records") +
    '<div class="grid-two">' +
    panel(barChart(portfolio.allocation_ngn), "Asset allocation • NGN") +
    panel('<div class="metric-row">' +
      '<div class="mini-metric"><label>Tracked goals</label><strong>' + goal.goals.length + '</strong></div>' +
      '<div class="mini-metric"><label>Data issues</label><strong>' + issue + '</strong></div>' +
      '<div class="mini-metric"><label>USD equivalent</label><strong>' +
      esc(portfolio.net_worth_usd == null ? "Unavailable" : money(portfolio.net_worth_usd, "USD")) + '</strong></div></div>' +
      '<h4 style="margin-top:25px">Financial resilience measures</h4>' +
      displayPairs(health.dimensions) +
      note(health.disclosure), "Financial health") + "</div>" +
    section("What deserves attention?", "Rule-based reviews, not instructions to trade") +
    '<div class="grid-two">' +
      panel(insightList(brief.recommended_reviews), "Priority reviews") +
      panel('<div class="metric-row">' +
        '<div class="mini-metric"><label>Missing-value alerts</label><strong>' + quality.critical + '</strong></div>' +
        '<div class="mini-metric"><label>Stale data alerts</label><strong>' + quality.warnings + '</strong></div>' +
        '<div class="mini-metric"><label>Assets valued</label><strong>' + portfolio.assets.length + '</strong></div></div>' +
        '<div style="margin-top:22px">' + (quality.issues.length
          ? table(["Type","Affected record"], quality.issues.slice(0, 7).map((i) => [i.type, i.name]))
          : '<div class="empty">No reported valuation issues. Coverage is limited to recorded assets.</div>') + '</div>',
        "Data confidence") + "</div>" +
    section("Fifteen connected intelligence modules", "Select a capability to open its analysis workspace") +
    '<div class="module-grid">' + MODULES.map((m,i) =>
      '<button class="module" data-route="' + esc(m.id) + '"><div class="module-top"><span class="icon">' +
      esc(["◫","◎","◈","◇","▤","〽","◉","▥","⊞","◷","✎","⇄","⬡","✧","▣"][i]) +
      '</span>' + badge(m.maturity) + '</div><h3>' + esc(m.name) + '</h3><p>' +
      esc(m.description) + '</p><div class="open">Open module →</div></button>').join("") + "</div>" +
    note(portfolio.disclosure);
  $("content").innerHTML = html;
  $("content").querySelectorAll("[data-route]").forEach((b) => b.addEventListener("click",
    () => { window.location.hash = "#" + b.dataset.route; }));
}

async function renderModule(module) {
  const subtitle = module.description + " • " + (module.maturity === "baseline"
    ? "Baseline capability; not a calibrated predictive model." : "Working analytical module.");
  const head = slide(module.name, subtitle, "");
  switch (module.id) {
    case "command": return renderCommandCenter();
    case "trajectory": return viewTrajectory(head);
    case "risk": return viewRisk(head);
    case "allocation": return viewAllocation(head);
    case "research": return viewResearch(head);
    case "signals": return viewSignals(head);
    case "events": return viewEvents(head);
    case "liquidity": return viewLiquidity(head);
    case "net-returns": return viewNetReturns(head);
    case "forecast": return viewForecast(head);
    case "journal": return viewJournal(head);
    case "rebalance": return viewRebalance(head);
    case "twin": return viewTwin(head);
    case "analyst": return viewAnalyst(head);
    case "backtest": return viewBacktest(head);
    default: $("content").innerHTML = panel("Unavailable", "Not implemented");
  }
}

async function viewTrajectory(head) {
  const data = await api("/goals");
  let html = head + panel(
    data.goals.length ? table(["Goal","Due","Projected future","Future target","Monthly required","Funding ratio"],
      data.goals.map((g) => [
        g.name, g.due_date || "Due", money(g.expected_future_ngn),
        money(g.target_future_ngn), money(g.required_monthly_ngn),
        g.goal_funding_ratio == null ? "—" : pct(g.goal_funding_ratio * 100),
      ])) : '<div class="empty">No financial goals configured yet. Start with a retirement or education goal.</div>',
    "Wealth trajectory • inflation-aware") +
    section("Set a long-term financial goal") +
    form("goal-form", "Goal definition", [
      field("name","Goal name","text","Retirement"),
      field("target_today_ngn","Goal amount in today's NGN","number","", {min:1,step:"any"}),
      field("due_date","Target date","date",""),
      field("monthly_contribution_ngn","Monthly contribution (NGN)","number","0",{min:0,step:"any"}),
      field("inflation_pct","Assumed annual inflation (%)","number","",{step:"any",min:-99}),
      field("expected_return_pct","Assumed annual return (%)","number","",{step:"any",min:-99}),
      field("priority","Priority 1 (high) to 5 (low)","number","3",{min:1,max:5,step:1}),
    ], "Save goal") +
    note("Goal funding assumes all current net worth is potentially available to every goal. Multiple goals compete for the same assets; they must be separately ring-fenced before relying on their independent ratios.");
  $("content").innerHTML = html;
  bindCreate("goal-form","/goals", (v) => ({
    name:v.name, target_today_ngn:numeric(v.target_today_ngn,"target"),
    due_date:v.due_date, monthly_contribution_ngn:numeric(v.monthly_contribution_ngn,"monthly"),
    inflation_pct:numeric(v.inflation_pct,"inflation"), expected_return_pct:numeric(v.expected_return_pct,"return"),
    priority:numeric(v.priority,"priority"),
  }));
}
async function viewRisk(head) {
  const r = await api("/risk");
  const historic = r.historical_model;
  $("content").innerHTML = head +
    '<div class="kpi-grid">' +
    metric("Class concentration HHI", r.class_concentration_hhi == null ? "N/A" : num(r.class_concentration_hhi,3),
      "Higher means more concentrated") +
    metric("Modelled positions", String(r.modelled_positions), "26+ aligned price returns required") +
    metric("Excluded positions", String(r.excluded_positions), "Missing data or history") +
    metric("Historical max drawdown", historic ? pct(historic.max_drawdown_pct) : "Unavailable", "Not a future loss bound") +
    "</div>" + section("Risk exposures", "Compare real concentrations and known gaps") +
    '<div class="grid-two">' + panel(barChart(r.allocation_pct), "Allocation breakdown") +
    panel(displayPairs(r.country_exposure_ngn), "Country exposure by NGN value") +
    panel(displayPairs(r.sector_exposure_ngn), "Sector exposure by NGN value") +
    panel(historic ? json(historic) : '<div class="empty">Insufficient aligned return history. Import valid price history for positions to calculate covariance, VaR and drawdown.</div>', "Historical risk model") +
    "</div>" + note(r.notes.join(" "));
}
async function viewAllocation(head) {
  const classes = ["NGX_STOCK","US_STOCK","ETF","MUTUAL_FUND","BOND","CASH"];
  const allFields = [
    field("initial_ngn","Capital (NGN)","number","",{min:0,step:"any"}),
    field("monthly_ngn","Monthly contribution (NGN)","number","",{min:0,step:"any"}),
    field("goal_ngn","Future nominal goal (NGN)","number","",{min:1,step:"any"}),
    field("years","Years","number","10",{min:1,max:40,step:1}),
    field("min_cash_pct","Minimum cash allocation (%)","number","0",{min:0,max:100,step:"any"}),
  ];
  let assumptionRows = '<div class="table-wrap"><table><thead><tr><th>Asset class</th><th>Return assumption % / year</th><th>Volatility assumption % / year</th><th>Mix A %</th><th>Mix B %</th></tr></thead><tbody>';
  for (const c of classes) {
    assumptionRows += "<tr><td>" + esc(c) + "</td>" +
      ["return_", "vol_", "mix_a_", "mix_b_"].map((prefix) =>
        '<td><input aria-label="' + esc(prefix + c) + '" name="' + esc(prefix + c) +
        '" type="number" step="any" required min="' + (prefix === "return_" ? "-99" : "0") +
        '" max="' + (prefix === "vol_" ? "200" : "1000") + '" placeholder="Required"></td>').join("") +
      "</tr>";
  }
  assumptionRows += "</tbody></table></div>";
  $("content").innerHTML = head +
    panel('<p class="muted">Evaluate two allocation alternatives using identical simulation draws. Enter all return, risk and weight assumptions explicitly. Each mix must total 100%.</p>' +
      '<form id="allocation-form" class="form-stack"><div class="form-grid">' +
      allFields.join("") + '</div>' + assumptionRows +
      '<button class="primary" type="submit">Compare candidate allocations</button></form>' +
      output("allocation-form-out"), "Capital allocation laboratory") +
    note("The model assumes independent monthly class shocks; realistic covariances, currency regimes, fees and taxes require calibrated inputs. This ranks assumptions, not stocks.");
  bindCalc("allocation-form","/allocation/compare",(v) => {
    const returns_pct={},volatility_pct={},a={},b={};
    classes.forEach((c) => {
      returns_pct[c]=numeric(v["return_"+c],c+" return");
      volatility_pct[c]=numeric(v["vol_"+c],c+" volatility");
      a[c]=numeric(v["mix_a_"+c],c+" A");b[c]=numeric(v["mix_b_"+c],c+" B");
    });
    return {
      candidates:{"Mix A":a,"Mix B":b},returns_pct,volatility_pct,
      initial_ngn:numeric(v.initial_ngn,"capital"),
      monthly_ngn:numeric(v.monthly_ngn,"contribution"),
      goal_ngn:numeric(v.goal_ngn,"goal"),years:numeric(v.years,"years"),
      min_cash_pct:numeric(v.min_cash_pct,"min cash"),
    };
  }, (r) => table(["Candidate","Probability of goal","Median","10th percentile","90th percentile"],
    r.ranked.map((x) => [x.name,pct(x.probability_goal*100),money(x.median_ngn),
      money(x.p10_ngn),money(x.p90_ngn)])) + note(r.disclosure.join(" ")));
}
async function viewResearch(head) {
  const [f,look,ins] = await Promise.all([api("/fundamentals"),api("/lookthrough"),api("/instruments")]);
  const opts=ins.map((i)=>[i.id,i.symbol+" • "+i.exchange]);
  $("content").innerHTML=head+
    '<div class="grid-two">' +
      panel(table(["Symbol","Year","Revenue","Net income","FCF","Source"],f.records.map((x)=>[
        x.symbol,x.year,num(x.revenue),num(x.net_income),num(x.free_cash_flow),x.source_url || "Unverified"
      ])), "Normalized company fundamentals") +
      panel(look.funds.length ? json(look.funds) :
        '<div class="empty">Add the reported constituents of ETFs or funds to uncover duplicated exposures.</div>', "Fund holdings look-through") +
    "</div>" + section("Investment research models","Explicit financial assumptions, source-linked statements") +
    '<div class="grid-two">' +
    form("dcf-form","Discounted cash flow", [
      field("base_free_cash_flow","Starting FCF (instrument currency)","number","",{step:"any"}),
      field("growth_pct","FCF growth (%)","number","",{step:"any"}),
      field("discount_pct","Discount rate (%)","number","",{step:"any"}),
      field("terminal_growth_pct","Terminal growth (%)","number","",{step:"any"}),
      field("years","Explicit projection years","number","5",{min:1,max:20}),
      field("net_debt","Net debt (same currency)","number","0",{step:"any"}),
      field("shares_outstanding","Shares outstanding","number","",{min:0.000001,step:"any"}),
    ],"Run DCF") +
    form("fundamental-form","Record reported fundamentals",[
      field("instrument_id","Security","select","",{options:opts}),
      field("fiscal_year","Financial year","number","2026",{min:1900,max:2100}),
      field("revenue","Revenue","number","",{step:"any",optional:true}),
      field("net_income","Net income","number","",{step:"any",optional:true}),
      field("free_cash_flow","Free cash flow","number","",{step:"any",optional:true}),
      field("total_debt","Total debt","number","",{step:"any",optional:true}),
      field("cash","Cash balance","number","",{step:"any",optional:true}),
      field("shares_outstanding","Shares outstanding","number","",{step:"any",optional:true}),
      field("source_url","Annual report URL","text","",{optional:true,wide:true}),
    ],"Store financial statement") + "</div>" + note("A DCF does not provide an authoritative fair value. The result should be sensitivity-tested before use.");
  bindCalc("dcf-form","/research/dcf", (v)=>({
    base_free_cash_flow:numeric(v.base_free_cash_flow,"FCF"),
    growth_pct:numeric(v.growth_pct,"growth"),discount_pct:numeric(v.discount_pct,"discount"),
    terminal_growth_pct:numeric(v.terminal_growth_pct,"terminal"),
    years:numeric(v.years,"years"),net_debt:numeric(v.net_debt,"debt"),
    shares_outstanding:numeric(v.shares_outstanding,"shares"),
  }), (r)=>'<div class="metric-row"><div class="mini-metric"><label>Equity value</label><strong>'+
      num(r.equity_value,2)+'</strong></div><div class="mini-metric"><label>Value / share</label><strong>'+
      num(r.fair_value_per_share,4)+'</strong></div><div class="mini-metric"><label>Terminal share</label><strong>'+
      pct(r.terminal_value_share_pct)+'</strong></div></div>'+json(r.forecast)+note(r.disclosure));
  bindCreate("fundamental-form","/fundamentals",(v)=> {
    const p={instrument_id:numeric(v.instrument_id,"security"),fiscal_year:numeric(v.fiscal_year,"year"),source_url:v.source_url};
    for(const k of ["revenue","net_income","free_cash_flow","total_debt","cash","shares_outstanding"]) p[k]=v[k]===""?null:numeric(v[k],k);
    return p;
  });
}
async function viewSignals(head) {
  const r=await api("/signals");
  $("content").innerHTML=head+
    panel(table(["Security","Market","Signal","20-point momentum","Annual vol"],
      r.items.map((x)=>[x.symbol,x.market,x.available?"Observed":"Insufficient history",
        x.available?pct(x.momentum_pct):"—",x.available?pct(x.annualized_vol_pct):"—"])),
      "Technical signals · descriptive only")+
    note("Momentum is not a validated investment recommendation. Signal evaluation, realistic costs, and chronological out-of-sample testing are required.");
}
async function viewEvents(head) {
  const [r,ins]=await Promise.all([api("/events"),api("/instruments")]);
  $("content").innerHTML=head+
    panel(table(["Date","Company","Event","Impact","Exposure"],
      r.events.map((e)=>[e.date,e.symbol,e.headline,e.thesis_impact,
        e.held_value_ngn==null?"Not held":money(e.held_value_ngn)])),
      "Financial events affecting tracked securities")+
    section("Record verifiable developments")+
    form("event-form","Financial event capture",[
      field("instrument_id","Security","select","",{options:ins.map((i)=>[i.id,i.symbol+" • "+i.exchange])}),
      field("occurred_on","Event date","date",TODAY),
      field("event_type","Type","select","EARNINGS",{options:["EARNINGS","DIVIDEND","DEBT","DILUTION","REGULATION","MACRO","OTHER"]}),
      field("headline","Event headline","text","",{wide:true}),
      field("observed_change","What changed?","textarea","",{wide:true}),
      field("source_url","Evidence URL","url","",{wide:true}),
      field("thesis_impact","Thesis impact","select","REVIEW",{options:["REVIEW","POSITIVE","NEGATIVE","NEUTRAL"]}),
      field("confidence","Review state","select","UNVERIFIED",{options:["UNVERIFIED","SOURCE_CHECKED"]}),
    ],"Record event")+note(r.note);
  bindCreate("event-form","/events",(v)=>({...v,instrument_id:numeric(v.instrument_id,"security")}));
}
async function viewLiquidity(head) {
  const report=await api("/liquidity");
  $("content").innerHTML=head+
    '<div class="kpi-grid">'+
    metric("Current cash",money(report.starting_cash_ngn),"Converted to NGN where rates exist")+
    metric("Emergency reserve",money(report.emergency_reserve_ngn),"6 months recurring expenses")+
    metric("Deployable now",money(report.deployable_ngn),"After forecast low and reserve")+
    metric("Lowest projected cash",money(report.lowest_balance_ngn),"Conservative outflows-first assumption")+
    "</div>"+section("Liquidity runway","Twelve-month forecast based on your obligations")+
    panel(table(["Month","Opening","Closing","Events"],
      report.months.map((x)=>[x.month,money(x.opening_ngn),money(x.closing_ngn),x.events.length])),
      "Cash-flow timeline")+
    section("Schedule income and obligations")+
    form("cashplan-form","New forecast entry",[
      field("name","Income or expense name","text",""),
      field("direction","Direction","select","OUT",{options:[["OUT","Expense"],["IN","Income"]]}),
      field("amount_ngn","Amount in NGN","number","",{min:0,step:"any"}),
      field("frequency","Repeat","select","MONTHLY",{options:["ONCE","MONTHLY","QUARTERLY","YEARLY"]}),
      field("start_date","Starts","date",TODAY),
      field("end_date","Ends (optional)","date","",{optional:true}),
    ],"Save cash-flow plan")+note(report.notes.join(" "));
  bindCreate("cashplan-form","/cash-plans",(v)=>({...v,amount_ngn:numeric(v.amount_ngn,"amount"),end_date:v.end_date||null}));
}
async function viewNetReturns(head) {
  const existing=await api("/tax-rules");
  $("content").innerHTML=head+
    panel(table(["Class","Sale tax %","Basis","Exit fees %","Effective"],
      existing.rules.map((r)=>[r.class,pct(r.sale_tax_pct),r.sale_tax_basis,pct(r.exit_fee_pct),r.effective_on])),
      "Tax and cost rules you've verified")+
    '<div class="grid-two">'+
    form("net-form","Net sale proceeds calculator",[
      field("gross_value","Market value","number","",{min:0,step:"any"}),
      field("cost_basis","Original cost","number","",{min:0,step:"any"}),
      field("tax_pct","Assumed tax rate (%)","number","",{min:0,max:100,step:"any"}),
      field("fee_pct","Assumed sale costs (%)","number","",{min:0,max:100,step:"any"}),
      field("tax_basis","Taxable basis","select","GAIN",{options:["GAIN","PROCEEDS"]}),
    ],"Calculate net return")+
    form("tax-form","Store verified instrument tax rule",[
      field("asset_class","Asset class","select","NGX_STOCK",{options:["NGX_STOCK","US_STOCK","ETF","MUTUAL_FUND","BOND","OTHER_SECURITY"]}),
      field("sale_tax_pct","Sale tax rate (%)","number","",{min:0,max:100,step:"any"}),
      field("exit_fee_pct","Exit fees (%)","number","",{min:0,max:100,step:"any"}),
      field("sale_tax_basis","Tax basis","select","GAIN",{options:["GAIN","PROCEEDS"]}),
      field("effective_on","Effective date","date",TODAY),
      field("notes","Legal source / caveats","textarea","",{wide:true}),
    ],"Save tax rule")+"</div>"+
    note("This module models entered rules. It does not determine current Nigerian or foreign tax law. Confirm tax treatment with a qualified adviser.");
  bindCalc("net-form","/net-return",(v)=>({
    gross_value:numeric(v.gross_value,"gross value"),cost_basis:numeric(v.cost_basis,"cost"),
    tax_pct:numeric(v.tax_pct,"tax"),fee_pct:numeric(v.fee_pct,"fees"),tax_basis:v.tax_basis,
  }), (r)=>'<div class="metric-row"><div class="mini-metric"><label>Net proceeds</label><strong>'+
    num(r.net_proceeds,2)+'</strong></div><div class="mini-metric"><label>Estimated tax</label><strong>'+
    num(r.estimated_tax,2)+'</strong></div><div class="mini-metric"><label>Net gain</label><strong>'+
    num(r.net_gain,2)+'</strong></div></div>'+note(r.disclosure));
  bindCreate("tax-form","/tax-rules",(v)=>({...v,
    sale_tax_pct:numeric(v.sale_tax_pct,"tax"),exit_fee_pct:numeric(v.exit_fee_pct,"exit fees")}));
}
async function viewForecast(head) {
  $("content").innerHTML=head+
    form("forecast-form","Probability of reaching your wealth goal",[
      field("initial_ngn","Starting investable capital (NGN)","number","",{min:0,step:"any"}),
      field("monthly_ngn","Monthly contribution (NGN)","number","",{min:0,step:"any"}),
      field("years","Time horizon, years","number","10",{min:1,max:60}),
      field("goal_ngn","Future nominal target (NGN)","number","",{min:1,step:"any"}),
      field("return_pct","Assumed nominal return (%/yr)","number","",{min:-99,step:"any"}),
      field("volatility_pct","Assumed annual volatility (%)","number","",{min:0,max:200,step:"any"}),
      field("inflation_pct","Assumed annual inflation (%)","number","",{step:"any"}),
    ],"Run Monte Carlo")+
    note("Normal monthly returns and fixed contributions are simplified assumptions. The output is conditional on these inputs, not a measured probability of financial success.");
  bindCalc("forecast-form","/forecast",(v)=>{
    const o={};for(const k of ["initial_ngn","monthly_ngn","years","goal_ngn","return_pct","volatility_pct","inflation_pct"])o[k]=numeric(v[k],k);return o;
  }, (r)=>'<div class="kpi-grid">'+
    metric("Probability of goal",pct(r.goal_probability*100,1),"Conditional on inputs")+
    metric("10th percentile",money(r.percentiles_ngn.p10),"Bad simulated outcome")+
    metric("Median",money(r.percentiles_ngn.p50),"Middle simulated outcome")+
    metric("90th percentile",money(r.percentiles_ngn.p90),"Good simulated outcome")+
    "</div>"+note(r.limits.join(" ")));
}
async function viewJournal(head) {
  const [r,ins]=await Promise.all([api("/decisions"),api("/instruments")]);
  $("content").innerHTML=head+
    '<div class="kpi-grid">'+
    metric("Recorded decisions",String(r.total),"Decision process ledger")+
    metric("Reviewed decisions",String(r.reviewed),"Outcome reflection")+
    metric("Recurring mistakes",String(Object.keys(r.mistakes).length),"Tagged behaviours")+
    metric("Patterns validated",r.patterns_reliable?"Sample ≥10":"Too few reviews","Descriptive only")+"</div>"+
    section("Decision history","Separate process quality from the investment outcome")+
    panel(table(["ID","Date","Action","Thesis","Process","Return"],
      r.entries.map((d)=>[d.id,d.date,d.action,d.thesis.slice(0,75),d.process_rating||"Not reviewed",pct(d.actual_return_pct)])),
      "Investment journal")+
    '<div class="grid-two">'+
    form("decision-form","Record new investment thesis",[
      field("decided_on","Decision date","date",TODAY),
      field("instrument_id","Security (optional)","select","",{optional:true,options:[["","No specific security"],...ins.map((i)=>[i.id,i.symbol])]}),
      field("action","Decision","select","BUY",{options:["BUY","SELL","HOLD","AVOID"]}),
      field("planned_horizon_months","Review horizon (months)","number","12",{min:1,max:600}),
      field("expected_return_pct","Expected return (%)","number","",{optional:true,step:"any"}),
      field("thesis","Why is this a good decision?","textarea","",{wide:true}),
      field("invalidation","What would prove this wrong?","textarea","",{wide:true}),
    ],"Save decision")+
    form("review-form","Review a past decision",[
      field("decision_id","Decision ID","number","",{min:1}),
      field("actual_return_pct","Actual return (%)","number","",{step:"any"}),
      field("benchmark_return_pct","Benchmark return (%)","number","",{optional:true,step:"any"}),
      field("process_rating","Process quality","select","GOOD",{options:["GOOD","POOR"]}),
      field("mistake_tags","Mistake tags, separated by commas","text","",{optional:true,wide:true}),
      field("notes","Retrospective learning","textarea","",{wide:true}),
    ],"Save review")+"</div>"+
    note(r.note);
  bindCreate("decision-form","/decisions",(v)=>({...v,
    instrument_id:v.instrument_id?numeric(v.instrument_id,"security"):null,
    planned_horizon_months:numeric(v.planned_horizon_months,"horizon"),
    expected_return_pct:v.expected_return_pct===""?null:numeric(v.expected_return_pct,"return")}));
  const f=$("review-form");
  f.addEventListener("submit",async(e)=>{
    e.preventDefault();const v=fvalues(f);
    try {
      const result=await post("/decisions/"+numeric(v.decision_id,"id")+"/review",{
        actual_return_pct:numeric(v.actual_return_pct,"return"),
        benchmark_return_pct:v.benchmark_return_pct===""?null:numeric(v.benchmark_return_pct,"benchmark"),
        process_rating:v.process_rating,mistake_tags:v.mistake_tags,notes:v.notes,
      });
      success("review-form-out",'<p class="success-text">Decision '+esc(result.id)+' reviewed.</p>');
    }catch(err){error("review-form-out",err);}
  });
}
async function viewRebalance(head) {
  const sheet=await api("/portfolio");
  const classes=Object.keys(sheet.allocation_ngn);
  if (!classes.length) { $("content").innerHTML=head+panel('<div class="empty">Fund accounts and record priced assets to establish an existing allocation.</div>',"Rebalancing prerequisites");return; }
  const share=100/classes.length;
  const fields=[field("contribution_ngn","New money available (NGN)","number","",{min:0,step:"any"})];
  classes.forEach((k)=>fields.push(field("target_"+k,"Target "+k+" (%)","number",share.toFixed(2),{min:0,max:100,step:"any"})));
  $("content").innerHTML=head+
    '<div class="grid-two">'+panel(barChart(sheet.allocation_ngn),"Current allocation")+
    panel('<p class="muted">Direct contributions to underweight classes without selling existing holdings.</p>'+
      '<form id="rebalance-form" class="form-grid">'+fields.join("")+
      '<div class="form-actions wide"><button class="primary" type="submit">Plan contribution</button></div></form>'+
      output("rebalance-form-out"),"Allocation targets")+"</div>"+
    note("This is a contribution planner, not an execution algorithm. Fees, tax lots, market liquidity and order sizing are excluded.");
  bindCalc("rebalance-form","/rebalance",(v)=>{
    const targets_pct={};classes.forEach((c)=>{targets_pct[c]=numeric(v["target_"+c],c);});
    return {targets_pct,contribution_ngn:numeric(v.contribution_ngn,"contribution")};
  },(r)=>table(["Asset class","New contribution","After %","Deviation %"],
      Object.keys(r.contribute_ngn).map((k)=>[k,money(r.contribute_ngn[k]),pct(r.after_pct[k]),pct(r.drift_pct[k])]))+note(r.disclosure));
}
async function viewTwin(head) {
  const sheet=await api("/portfolio");
  const fields=[
    field("emergency_expense_ngn","One-time emergency expense (NGN)","number","0",{min:0,step:"any"}),
    field("monthly_income_loss_ngn","Monthly income lost (NGN)","number","0",{min:0,step:"any"}),
    field("income_loss_months","Income loss duration (months)","number","0",{min:0,max:60,step:1}),
  ];
  Object.keys(sheet.allocation_ngn).forEach((k)=>fields.push(
    field("shock_"+k,"Shock to "+k+" (%)","number","0",{min:-100,max:1000,step:"any"})
  ));
  $("content").innerHTML=head+
    '<div class="kpi-grid">'+metric("Starting net worth",money(sheet.net_worth_ngn),"Recorded assets and liabilities")+
    metric("Asset classes",String(Object.keys(sheet.allocation_ngn).length),"Shock independently")+
    metric("Existing liabilities",money(sheet.liabilities_ngn),"Remain unchanged in scenarios")+
    metric("Valuation issues",String(sheet.data_issues.length),"Scenario excludes unknown values")+"</div>"+
    section("Stress your entire balance sheet","Model market shocks alongside reduced income")+
    form("stress-form","Financial stress laboratory",fields,"Run scenario")+
    note("A balance-sheet shock is not a forecast. Joint asset correlations, tax effects and margin liquidation are not represented.");
  bindCalc("stress-form","/twin/stress",(v)=>{
    const shocks_pct={};Object.keys(sheet.allocation_ngn).forEach((k)=>shocks_pct[k]=numeric(v["shock_"+k],k));
    return {shocks_pct,emergency_expense_ngn:numeric(v.emergency_expense_ngn,"expense"),
      monthly_income_loss_ngn:numeric(v.monthly_income_loss_ngn,"income loss"),
      income_loss_months:numeric(v.income_loss_months,"months")};
  },(r)=>'<div class="metric-row">'+
      '<div class="mini-metric"><label>Before shock</label><strong>'+money(r.net_worth_before)+'</strong></div>'+
      '<div class="mini-metric"><label>After shock</label><strong>'+money(r.net_worth_after)+'</strong></div>'+
      '<div class="mini-metric"><label>Wealth change</label><strong>'+pct(r.change_pct)+'</strong></div></div>'+
      barChart(r.after_classes)+note(r.disclosure));
}
async function viewAnalyst(head) {
  const brief=await api("/analyst/brief");
  $("content").innerHTML=head+
    '<div class="hero"><div><span class="eyebrow">EVIDENCE BEFORE OPINION</span>'+
    '<h2>An analyst that knows when not to recommend action.</h2>'+
    '<p>Grounded checks against actual portfolio, risk, liquidity and data completeness. No fabricated live market quotes.</p></div></div>'+
    '<div class="grid-two">'+panel(insightList(brief.recommended_reviews),"Recommended investigations")+
    panel(displayPairs(brief.summary),"Verified source calculations")+"</div>"+
    section("Ask the research analyst","Opt-in external LLM explanation — the deterministic briefing remains private")+
    form("analyst-form","Generate a grounded explanation",[
      field("question","Question about your financial position","textarea","What should I investigate to improve my wealth plan?",{wide:true}),
      field("consent_to_external_processing","Share aggregate computed figures with external model?","select","false",{
        options:[["false","No — keep data local"],["true","Yes — I consent to sending the question, aggregate net worth/liquidity/risk metrics and review triggers"]],
        wide:true
      }),
    ],"Generate research explanation")+
    section("Source contracts","Inspect the authoritative calculations")+
    panel(table(["Dataset endpoint","What it answers"],
      brief.source_paths.map((p)=>[p,"Computed from the recorded financial ledger"])),"Evidence lineage")+
    note(brief.disclosure)+note("An external AI key and model name must be set in the server environment. Generative explanations are not authoritative calculations, verified citations or trade instructions.");
  bindCalc("analyst-form","/analyst/ask",(v)=>{
    if(v.consent_to_external_processing!=="true")throw new Error("Explicit external-processing consent is required.");
    return {question:v.question,consent_to_external_processing:true};
  },(r)=>panel('<p style="white-space:pre-wrap">'+esc(r.answer)+'</p>',"LLM research output")+
     note("Data shared: "+r.external_data_shared+". "+r.disclaimer));
}
async function viewBacktest(head) {
  $("content").innerHTML=head+form("backtest-form","Strategy experiment • chronological holdout",[
    field("strategy_pct","Strategy returns (%) one number per comma","textarea","",{wide:true}),
    field("benchmark_pct","Benchmark returns (%) same dates","textarea","",{wide:true}),
    field("fee_pct","Estimated cost per period (%)","number","0",{min:0,max:100,step:"any"}),
    field("train_fraction","Development share (0.5–0.9)","number","0.7",{min:.5,max:.9,step:.05}),
  ],"Evaluate holdout performance")+
  section("ML research validation","Fit a logistic classifier on time-ordered, pre-labelled features; compare to a no-skill baseline")+
  form("ml-form","Chronological ML evaluation",[
    field("feature_names","Comma-separated numeric feature names","text","momentum,quality",{wide:true}),
    field("dates","ISO dates in ascending order, comma-separated","textarea","",{wide:true}),
    field("features","Numeric feature matrix as JSON arrays, e.g. [[0.1,2],[0.4,3]]","textarea","",{wide:true}),
    field("labels","Binary future outcomes 0/1 separated by commas","textarea","",{wide:true}),
    field("label_horizon","Embargo in observation rows","number","5",{min:1,max:60}),
    field("holdout_fraction","Holdout proportion","number","0.25",{min:.15,max:.4,step:.05}),
  ],"Evaluate classifier")+
  note("ML validation requires 100+ dated observations, future-outcome labels, confirmed point-in-time feature availability and a chronological embargo. It does not predict a specific security or place trades.");
  bindCalc("backtest-form","/backtest",(v)=>{
    const values=(key)=>v[key].split(/[\s,;]+/).filter(Boolean).map((x)=>numeric(x,key));
    return {strategy_pct:values("strategy_pct"),benchmark_pct:values("benchmark_pct"),
      fee_pct:numeric(v.fee_pct,"fee"),train_fraction:numeric(v.train_fraction,"fraction")};
  },(r)=>table(["Period set","Strategy return","Benchmark return","Strategy worst drawdown","Excess per period"],
    Object.entries(r.segments).map(([k,x])=>[k,pct(x.strategy.total_return_pct),
      pct(x.benchmark.total_return_pct),pct(x.strategy.max_drawdown_pct),
      pct(x.average_excess_pct_per_period,3)])) + note(r.caveats.join(" ")));
  bindCalc("ml-form","/ml/evaluate",(v)=>{
    let features;
    try{features=JSON.parse(v.features);}catch(e){throw new Error("Feature matrix must be a JSON array of numeric arrays.");}
    return {feature_names:v.feature_names.split(",").map(x=>x.trim()).filter(Boolean),
      dates:v.dates.split(/[\s,;]+/).filter(Boolean),
      features,labels:v.labels.split(/[\s,;]+/).filter(Boolean).map((x)=>numeric(x,"label")),
      label_horizon:numeric(v.label_horizon,"label horizon"),
      holdout_fraction:numeric(v.holdout_fraction,"holdout")};
  },(r)=>'<div class="metric-row">'+
    '<div class="mini-metric"><label>Model Brier loss</label><strong>'+num(r.metrics.model_brier,5)+'</strong></div>'+
    '<div class="mini-metric"><label>Baseline Brier loss</label><strong>'+num(r.metrics.baseline_brier,5)+'</strong></div>'+
    '<div class="mini-metric"><label>Holdout ROC AUC</label><strong>'+num(r.metrics.holdout_roc_auc,3)+'</strong></div></div>'+
    '<p>'+(r.beats_baseline_on_brier?'Model beat the constant baseline in this single holdout.':'Model did not beat the constant baseline on holdout Brier score.')+'</p>'+
    table(["Feature","Standardized coefficient"],r.standardized_coefficients.map((x)=>[x.feature,num(x.coefficient,4)]))+
    note(r.warnings.join(" ")));
}
