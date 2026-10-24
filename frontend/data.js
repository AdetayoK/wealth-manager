"use strict";
async function renderDataWorkspace() {
  const [accounts,instruments,positions,ledger] = await Promise.all([
    api("/accounts"),api("/instruments"),api("/holdings"),api("/trades")
  ]);
  const accountOpts=accounts.map((a)=>[a.id,a.name+" ("+a.currency+")"]);
  const instrumentOpts=instruments.map((i)=>[i.id,i.symbol+" ("+i.currency+" • "+i.exchange+")"]);
  const accountField=(id="account_id")=>field(id,"Account","select","",{options:accountOpts});
  const instrumentField=(id="instrument_id")=>field(id,"Instrument","select","",{options:instrumentOpts});
  const content=slide("Portfolio data workspace",
    "Create accounts, manage positions and import source-identified market data.","")+
    '<div class="hero"><div><span class="eyebrow">THE FINANCIAL SOURCE OF TRUTH</span>'+
    '<h2>Your analysis is only as reliable as your records.</h2>'+
    '<p>Record cash, holdings, exchange rates and prices before relying on scenario and risk models.</p></div></div>'+
    '<div class="kpi-grid">'+
      metric("Cash / broker accounts",String(accounts.length),"Multi-currency ledger")+
      metric("Securities tracked",String(instruments.length),"NGX, US, global and funds")+
      metric("Open positions",String(positions.positions.length),"Owned assets with quantity > 0")+
      metric("Recorded trades",String(ledger.length),"Buy / sell transactions")+"</div>"+
    section("Current holdings","Only values with valid recorded prices and FX can be translated to naira")+
    panel(table(["Symbol","Class","Account","Quantity","Price","Value (local)","NGN equivalent"],
      positions.positions.map((p)=>[p.symbol,p.asset_class,p.account,num(p.quantity,5),
        num(p.price,4),p.value_native==null?"Unpriced":num(p.value_native,2),
        p.value_ngn==null?"Not convertible":money(p.value_ngn)])),
      "Consolidated investment positions")+
    section("Account and instrument registry","Set up the canonical records")+
    '<div class="grid-two">'+
    form("new-account","Add a cash or brokerage account",[
      field("name","Account label","text",""),
      field("currency","Account currency","text","NGN"),
      field("kind","Kind","select","BROKER",{options:["BROKER","CASH"]}),
    ],"Create account")+
    form("new-instrument","Register a security or fund",[
      field("symbol","Ticker / symbol","text",""),
      field("name","Security name","text",""),
      field("asset_class","Asset class","select","NGX_STOCK",{options:["NGX_STOCK","US_STOCK","ETF","MUTUAL_FUND","BOND","OTHER_SECURITY"]}),
      field("currency","Pricing currency","text","NGN"),
      field("exchange","Exchange (e.g. XNSA or XNAS)","text",""),
      field("country","Country code","text","NG"),
      field("sector","Industry / sector","text",""),
      field("domicile","Fund domicile code","text","",{optional:true}),
      field("isin","ISIN","text","",{optional:true}),
    ],"Register instrument")+"</div>"+
    section("Record cash, trades and valuations","All writes are authenticated and anti-CSRF protected")+
    '<div class="grid-two">'+
    form("new-cash","Deposit, withdraw or record income",[
      accountField(),field("as_of","Value date","date",TODAY),
      field("kind","Entry type","select","DEPOSIT",{options:["DEPOSIT","WITHDRAWAL","DIVIDEND","INTEREST","EXPENSE","FEE","ADJUSTMENT"]}),
      field("amount","Signed amount in account currency","number","",{step:"any"}),
      field("note","Reference / explanation","text","",{wide:true}),
    ],"Record cash movement")+
    form("new-trade","Record an investment trade",[
      accountField(),instrumentField(),
      field("as_of","Trade date","date",TODAY),
      field("side","Side","select","BUY",{options:["BUY","SELL"]}),
      field("quantity","Quantity (units)","number","",{min:0.00000001,step:"any"}),
      field("price","Unit price","number","",{min:0,step:"any"}),
      field("fees","Brokerage fees","number","0",{min:0,step:"any"}),
      field("external_ref","Broker trade reference (optional)","text","",{optional:true}),
    ],"Record trade")+
    form("new-price","Record an official or manual close",[
      instrumentField(),field("as_of","Close date","date",TODAY),
      field("close","Unit close in instrument currency","number","",{min:0.00000001,step:"any"}),
      field("source","Price provider / document","text","manual"),
    ],"Save price")+
    form("new-fx","Set an exchange rate",[
      field("base","Base currency","text","USD"),
      field("quote","Quote currency","text","NGN"),
      field("as_of","Observed on","date",TODAY),
      field("rate","Quote units per 1 base unit","number","",{min:0.00000001,step:"any"}),
      field("source","Rate source","text","manual"),
    ],"Save FX rate")+
    form("new-item","Other assets and liabilities",[
      field("name","Asset or liability name","text",""),
      field("kind","Type","select","ASSET",{options:["ASSET","LIABILITY"]}),
      field("category","Category","text","PROPERTY"),
      field("currency","Currency","text","NGN"),
      field("amount","Valuation / outstanding balance","number","",{min:0,step:"any"}),
      field("valued_on","Valuation date","date",TODAY),
      field("notes","Source and methodology","textarea","",{wide:true}),
    ],"Save asset / liability")+
    form("cash-transfer","Move cash between accounts",[
      field("from_account_id","Source account","select","",{options:accountOpts}),
      field("to_account_id","Destination account","select","",{options:accountOpts}),
      field("as_of","Transfer date","date",TODAY),
      field("amount","Amount in shared currency","number","",{min:0.00000001,step:"any"}),
      field("note","Transfer reference","text","",{optional:true,wide:true}),
    ],"Transfer without creating income")+
    "</div>"+
    section("Prices in bulk","All rows validated before database writes; duplicates upsert by instrument and date")+
    panel('<p class="muted">CSV columns: <code>symbol,exchange,date,close,source</code>. '+
      'Use an exchange string exactly as registered. Dates use YYYY-MM-DD; close is denominated in instrument currency.</p>'+
      '<form id="csv-form" class="form-stack" enctype="multipart/form-data">'+
      '<label>Price history CSV<input name="upload" type="file" accept=".csv,text/csv" required></label>'+
      '<button type="submit" class="primary">Validate and import CSV</button></form>'+output("csv-form-out"),
      "Source-identified prices")+
    section("US securities price provider","Optional manually triggered source-labelled daily quote ingestion")+
    form("us-price-sync","Sync a US-listed security",[
      field("instrument_id","USD equity or US-listed ETF","select","",{options:instruments.filter((i)=>i.currency==="USD"&&(i.asset_class==="US_STOCK"||(i.asset_class==="ETF"&&["XNAS","XNYS","ARCX"].includes(i.exchange)))).map((i)=>[i.id,i.symbol+" • "+i.exchange])}),
    ],"Sync latest supported daily closes")+
    note("Requires ALPHAVANTAGE_API_KEY in the server .env. Raw end-of-day closes do not include dividend/split-adjusted total return; provider usage limits apply.")+
    section("Registered accounts","Trade funding comes out of the same-currency account")+
    panel(table(["Name","Currency","Kind","Available cash"],
      accounts.map((a)=>[a.name,a.currency,a.kind,money(a.balance,a.currency)])), "Cash inventory")+
    note("This first release requires manual entries or imported prices. It never invents exchange rates, financial reports, NAVs, ETF constituents or corporate actions.");
  $("content").innerHTML=content;

  bindCreate("new-account","/accounts",(v)=>v);
  bindCreate("new-instrument","/instruments",(v)=>v);
  bindCreate("new-cash","/cash",(v)=>({
    ...v, account_id:numeric(v.account_id,"account"),amount:numeric(v.amount,"amount")
  }));
  bindCreate("new-trade","/trades",(v)=>({
    ...v,account_id:numeric(v.account_id,"account"),instrument_id:numeric(v.instrument_id,"security"),
    quantity:numeric(v.quantity,"quantity"),price:numeric(v.price,"price"),
    fees:numeric(v.fees,"fees"),external_ref:v.external_ref||null,
  }));
  bindCreate("new-price","/prices",(v)=>({
    ...v,instrument_id:numeric(v.instrument_id,"security"),close:numeric(v.close,"price")
  }));
  bindCreate("new-fx","/fx",(v)=>({...v,rate:numeric(v.rate,"rate")}));
  bindCreate("new-item","/balance-items",(v)=>({...v,amount:numeric(v.amount,"amount")}));
  bindCreate("cash-transfer","/transfers",(v)=>({
    ...v,from_account_id:numeric(v.from_account_id,"source"),
    to_account_id:numeric(v.to_account_id,"destination"),amount:numeric(v.amount,"amount")
  }));
  bindCalc("us-price-sync","/providers/us-daily-sync",(v)=>({instrument_id:numeric(v.instrument_id,"US security")}),
    (r)=>"<p class=\"success-text\">Synchronized "+esc(r.rows)+" daily prices for "+esc(r.symbol)+".</p>"+json(r));
  const uploader=$("csv-form");
  uploader.addEventListener("submit",async (event)=>{
    event.preventDefault();
    const btn=uploader.querySelector("button");
    btn.disabled=true;
    try {
      const result=await api("/import/prices", {method:"POST",body:new FormData(uploader)});
      success("csv-form-out",'<p class="success-text">Imported '+esc(result.imported)+
        ' price rows, with date-based upsert.</p>');
    }catch(err){error("csv-form-out",err);}finally{btn.disabled=false;}
  });
}
