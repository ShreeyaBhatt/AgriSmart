<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AgriSmart AI — Field Notes</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;1,9..144,500&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#17140f;
    --bg-panel:#211c15;
    --bg-panel-2:#2a2319;
    --line:#3c3325;
    --line-soft:#2c2619;
    --text:#ece4d3;
    --text-mute:#a99b85;
    --text-dim:#8a7c68;
    --green:#8bc34a;
    --green-deep:#5c8a3f;
    --amber:#e3a857;
    --sky:#74a7bd;
    --paper:#efe8d6;
    --paper-ink:#241f16;
    --radius-card: 3px;
  }
  *{box-sizing:border-box;}
  html{scroll-behavior:smooth;}
  body{
    margin:0;
    background:var(--bg);
    background-image:
      radial-gradient(ellipse at 15% -10%, rgba(139,195,74,0.07), transparent 45%),
      radial-gradient(ellipse at 90% 10%, rgba(227,168,87,0.06), transparent 40%);
    color:var(--text);
    font-family:'IBM Plex Sans', sans-serif;
    line-height:1.55;
    -webkit-font-smoothing:antialiased;
  }
  h1,h2,h3,h4{ font-family:'Fraunces', serif; font-weight:600; margin:0; color:var(--paper); letter-spacing:-0.01em;}
  a{color:var(--green);}
  .mono{ font-family:'IBM Plex Mono', monospace; }
  .wrap{ max-width:1080px; margin:0 auto; padding:0 28px; }
  ::selection{ background:var(--green-deep); color:#fff;}

  /* ---------- top ribbon ---------- */
  .ribbon{
    border-bottom:1px solid var(--line);
    padding:14px 0;
    background:linear-gradient(180deg, rgba(0,0,0,0.15), transparent);
  }
  .ribbon .wrap{ display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;}
  .ribbon-tag{
    font-family:'IBM Plex Mono', monospace; font-size:12.5px; color:var(--text-dim);
    display:flex; align-items:center; gap:8px;
  }
  .ribbon-tag .dot{width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);}
  .ribbon-brand{ display:flex; align-items:center; gap:9px; font-family:'Fraunces',serif; font-size:19px; color:var(--paper); font-weight:600;}

  /* ---------- hero ---------- */
  .hero{ padding:76px 0 40px; position:relative; }
  .hero .kicker{
    color:var(--amber); font-family:'IBM Plex Mono', monospace; font-size:13.5px;
    margin-bottom:18px; display:flex; align-items:center; gap:10px;
  }
  .hero .kicker svg{ width:16px;height:16px; }
  .hero h1{ font-size:clamp(40px, 6vw, 66px); line-height:1.02; max-width:14ch;}
  .hero h1 em{ font-style:italic; color:var(--green); }
  .hero p.lead{
    margin-top:22px; max-width:56ch; font-size:18px; color:var(--text-mute);
  }
  .hero .badges{ display:flex; gap:10px; margin-top:28px; flex-wrap:wrap; }
  .pill{
    border:1px solid var(--line); border-radius:100px; padding:6px 14px;
    font-family:'IBM Plex Mono', monospace; font-size:12.5px; color:var(--text-mute);
    display:flex; align-items:center; gap:7px; background:rgba(255,255,255,0.015);
  }
  .pill svg{ width:13px; height:13px; color:var(--green); }

  /* ---------- flow strip ---------- */
  .flow{ margin-top:56px; }
  .flow-row{
    display:flex; align-items:stretch; gap:0; flex-wrap:wrap; row-gap:18px;
  }
  .flow-node{
    flex:1 1 150px; min-width:150px;
    border:1px solid var(--line); background:var(--bg-panel);
    padding:18px 16px; position:relative;
    display:flex; flex-direction:column; gap:10px;
  }
  .flow-node:first-child{ border-radius:4px 0 0 4px; }
  .flow-node:last-child{ border-radius:0 4px 4px 0; border-color:var(--green-deep); background:linear-gradient(160deg, rgba(139,195,74,0.10), var(--bg-panel));}
  .flow-node .icon{ width:26px; height:26px; color:var(--green); }
  .flow-node .step-label{ font-family:'IBM Plex Mono', monospace; font-size:11px; color:var(--text-dim); }
  .flow-node .step-title{ font-family:'Fraunces', serif; font-size:16.5px; color:var(--paper); font-weight:500;}
  .flow-arrow{
    flex:0 0 34px; display:flex; align-items:center; justify-content:center;
    color:var(--text-dim);
  }
  .flow-arrow svg{width:18px;height:18px;}
  @media (max-width:760px){ .flow-arrow{ display:none; } .flow-node{ border-radius:4px !important; border-color:var(--line) !important; background:var(--bg-panel) !important;} }

  .branch-note{
    margin-top:14px; padding-left:16px; border-left:2px dashed var(--line);
    color:var(--text-dim); font-size:13.5px; font-family:'IBM Plex Mono', monospace;
  }

  /* ---------- section shell ---------- */
  section{ padding:70px 0; border-top:1px solid var(--line-soft); }
  .section-head{ display:flex; align-items:baseline; gap:16px; margin-bottom:36px; flex-wrap:wrap;}
  .section-num{ font-family:'IBM Plex Mono', monospace; color:var(--amber); font-size:14px; }
  .section-head h2{ font-size:clamp(26px,3.4vw,34px); }
  .section-sub{ color:var(--text-mute); max-width:62ch; margin-top:10px; font-size:15.5px; }

  /* ---------- module cards (field-note / seed packet) ---------- */
  .modules{ display:grid; grid-template-columns:repeat(auto-fit, minmax(280px,1fr)); gap:18px; }
  .module-card{
    background:var(--bg-panel);
    border:1px solid var(--line);
    border-radius:4px;
    padding:22px 22px 20px;
    position:relative;
    overflow:hidden;
    transition:transform .18s ease, border-color .18s ease;
  }
  .module-card:hover{ transform:translateY(-3px); border-color:var(--green-deep); }
  .module-card::before{
    content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--green-deep);
  }
  .module-card.dim::before{ background:var(--line); }
  .module-card.dim{ opacity:0.6; }
  .module-top{ display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
  .module-id{ font-family:'IBM Plex Mono',monospace; font-size:12px; color:var(--text-dim); }
  .module-title{ font-family:'Fraunces', serif; font-size:19px; color:var(--paper); margin-top:6px; font-weight:500;}
  .stamp{
    font-family:'IBM Plex Mono', monospace; font-size:11px; padding:4px 10px;
    border:1.5px dashed var(--green); color:var(--green); border-radius:100px;
    transform:rotate(-4deg); white-space:nowrap; flex-shrink:0;
  }
  .stamp.off{ border-color:var(--text-dim); color:var(--text-dim); }
  .module-desc{ color:var(--text-mute); font-size:14.5px; margin-top:12px; }
  .module-path{
    margin-top:14px; font-family:'IBM Plex Mono', monospace; font-size:12px;
    color:var(--sky); background:rgba(116,167,189,0.08); padding:6px 10px; border-radius:3px;
    display:inline-block; word-break:break-all;
  }

  /* ---------- db split ---------- */
  .split{ display:grid; grid-template-columns:1fr 1fr; gap:2px; background:var(--line); border:1px solid var(--line); border-radius:4px; overflow:hidden; }
  @media (max-width:700px){ .split{ grid-template-columns:1fr; } }
  .split > div{ background:var(--bg-panel); padding:26px 26px; }
  .split h4{ font-size:17px; display:flex; align-items:center; gap:9px; margin-bottom:10px;}
  .split h4 svg{ width:18px; height:18px; }
  .split p{ color:var(--text-mute); font-size:14.5px; }
  .split .tag{ font-family:'IBM Plex Mono',monospace; font-size:11.5px; color:var(--text-dim); margin-top:12px; display:block;}

  /* ---------- architecture ---------- */
  .arch{
    border:1px solid var(--line); border-radius:6px; padding:36px 30px; background:var(--bg-panel);
    display:flex; flex-direction:column; align-items:center; gap:0;
  }
  .arch-box{
    border:1px solid var(--line); background:var(--bg-panel-2); border-radius:4px;
    padding:14px 22px; text-align:center; font-family:'IBM Plex Mono', monospace; font-size:13px; color:var(--paper);
  }
  .arch-box.accent{ border-color:var(--green-deep); background:linear-gradient(160deg, rgba(139,195,74,0.12), var(--bg-panel-2)); }
  .arch-connector{ width:1px; height:26px; background:var(--line); }
  .arch-branches{
    display:grid; grid-template-columns:repeat(auto-fit, minmax(150px,1fr)); gap:14px;
    width:100%; margin-top:10px;
  }
  .arch-branches .arch-box{ font-size:12px; padding:12px 14px; }
  .arch-row{ display:flex; gap:16px; width:100%; justify-content:center; flex-wrap:wrap; }

  /* ---------- endpoints table ---------- */
  table.ledger{ width:100%; border-collapse:collapse; font-size:13.5px; }
  table.ledger th{
    text-align:left; font-family:'IBM Plex Mono', monospace; font-weight:500; font-size:11.5px;
    color:var(--text-dim); padding:10px 14px; border-bottom:1px solid var(--line);
  }
  table.ledger td{
    padding:12px 14px; border-bottom:1px solid var(--line-soft); color:var(--text-mute); vertical-align:top;
  }
  table.ledger tr:hover td{ background:rgba(255,255,255,0.015); }
  table.ledger td.method{ font-family:'IBM Plex Mono', monospace; color:var(--amber); font-size:12px; white-space:nowrap;}
  table.ledger td.endpoint{ font-family:'IBM Plex Mono', monospace; color:var(--paper); font-size:12.5px;}
  table.ledger td.auth{ font-family:'IBM Plex Mono', monospace; font-size:12px; color:var(--sky); white-space:nowrap;}

  /* ---------- metrics ---------- */
  .metrics{ display:grid; grid-template-columns:repeat(auto-fit, minmax(180px,1fr)); gap:2px; background:var(--line); border:1px solid var(--line); border-radius:4px; overflow:hidden; }
  .metric{ background:var(--bg-panel); padding:26px 20px; }
  .metric .num{ font-family:'Fraunces', serif; font-size:36px; color:var(--green); font-weight:600; }
  .metric .lbl{ font-size:12.5px; color:var(--text-dim); margin-top:6px; font-family:'IBM Plex Mono', monospace;}

  /* ---------- sources table ---------- */
  .sources{ display:flex; flex-direction:column; gap:10px; }
  .source-row{
    display:grid; grid-template-columns:1.3fr 1.8fr 1fr; gap:16px; padding:14px 16px;
    border:1px solid var(--line-soft); border-radius:4px; align-items:center; font-size:13.5px;
  }
  .source-row .src-name{ font-family:'IBM Plex Mono', monospace; color:var(--paper); font-size:13px;}
  .source-row .src-use{ color:var(--text-mute); }
  .source-row .src-lic{ color:var(--sky); font-family:'IBM Plex Mono', monospace; font-size:12px; text-align:right;}
  @media (max-width:640px){ .source-row{ grid-template-columns:1fr; text-align:left;} .source-row .src-lic{text-align:left;} }

  /* ---------- stack chips ---------- */
  .stack-group{ margin-bottom:22px; }
  .stack-group h4{ font-family:'IBM Plex Mono', monospace; font-size:12px; color:var(--text-dim); font-weight:500; margin-bottom:12px; }
  .chips{ display:flex; flex-wrap:wrap; gap:8px; }
  .chip{
    border:1px solid var(--line); border-radius:100px; padding:6px 13px; font-size:12.5px;
    color:var(--text-mute); font-family:'IBM Plex Mono', monospace; background:var(--bg-panel);
  }

  /* ---------- repo tree ---------- */
  .tree{
    background:var(--bg-panel); border:1px solid var(--line); border-radius:5px; padding:22px 24px;
    font-family:'IBM Plex Mono', monospace; font-size:13px; color:var(--text-mute); overflow-x:auto;
  }
  .tree .folder{ color:var(--amber); }
  .tree .desc{ color:var(--text-dim); }

  /* ---------- footer / originality ---------- */
  footer{ padding:60px 0 90px; }
  .field-note{
    border:1px solid var(--line); border-radius:6px; padding:32px 34px; background:var(--bg-panel);
    position:relative;
  }
  .field-note::after{
    content:""; position:absolute; top:18px; right:18px; width:34px; height:34px;
    opacity:0.5;
  }
  .field-note h3{ font-size:20px; margin-bottom:14px; }
  .field-note ul{ margin:0; padding-left:20px; color:var(--text-mute); font-size:14.5px; }
  .field-note li{ margin-bottom:8px; }
  .foot-meta{ margin-top:34px; display:flex; justify-content:space-between; color:var(--text-dim); font-size:12.5px; font-family:'IBM Plex Mono', monospace; flex-wrap:wrap; gap:10px;}

  code.inline{ font-family:'IBM Plex Mono', monospace; background:rgba(255,255,255,0.05); padding:2px 6px; border-radius:3px; color:var(--paper); font-size:0.92em;}

  @keyframes sprout{
    0%{ transform:scaleY(0.2) translateY(6px); opacity:0; transform-origin:bottom;}
    100%{ transform:scaleY(1) translateY(0); opacity:1; transform-origin:bottom;}
  }
  .sprout-anim{ animation: sprout 0.9s cubic-bezier(.2,.9,.3,1.2) both; }
</style>
</head>
<body>

<div class="ribbon">
  <div class="wrap">
    <div class="ribbon-brand">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" style="color:var(--green)"><path d="M12 21c0-6 4-9 8-10-1 5-3 10-8 10Z"/><path d="M12 21c0-7-4-11-9-12 1 6 3 12 9 12Z"/></svg>
      AgriSmart AI
    </div>
    <div class="ribbon-tag"><span class="dot"></span> SIH 2026 internal hackathon · L. J. Institute · PS-1 / C-433</div>
  </div>
</div>

<div class="hero">
  <div class="wrap">
    <div class="kicker">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      Field-tested build, not a slide deck
    </div>
    <h1>A farm app that answers the three questions a farmer actually <em>asks</em>.</h1>
    <p class="lead">What's wrong with this leaf. What should I do about my soil. What does the weather mean for tomorrow. AgriSmart AI logs a farmer in, remembers their plots, and answers all three — grounded in real soil data, a real forecast, and a disease model that admits when it isn't sure.</p>
    <div class="badges">
      <span class="pill"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg> 4 of 6 modules shipped</span>
      <span class="pill"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg> 47 passing tests</span>
      <span class="pill"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18M18.7 8l-5.1 5.1-3-3L4.5 16.2"/></svg> 0.966 macro-F1, held-out val</span>
    </div>

    <div class="flow">
      <div class="flow-row">
        <div class="flow-node sprout-anim">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="7" r="3"/></svg>
          <span class="step-label">01 — enter</span>
          <span class="step-title">Login</span>
        </div>
        <div class="flow-arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg></div>
        <div class="flow-node sprout-anim" style="animation-delay:.08s">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2 2 9l10 5 10-5-10-7Z"/><path d="M6 12v7c0 1.1 2.7 2 6 2s6-.9 6-2v-7"/></svg>
          <span class="step-label">02 — orient</span>
          <span class="step-title">My Farm</span>
        </div>
        <div class="flow-arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg></div>
        <div class="flow-node sprout-anim" style="animation-delay:.16s">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 7h16l-1.5 12.5a2 2 0 01-2 1.5H7.5a2 2 0 01-2-1.5L4 7Z"/><path d="M9 7V5a3 3 0 016 0v2"/></svg>
          <span class="step-label">03 — capture</span>
          <span class="step-title">Scan a leaf</span>
        </div>
        <div class="flow-arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg></div>
        <div class="flow-node sprout-anim" style="animation-delay:.24s">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/><circle cx="12" cy="12" r="3"/></svg>
          <span class="step-label">04 — decide</span>
          <span class="step-title">Diagnosis + Grad-CAM + what to do</span>
        </div>
      </div>
      <div class="branch-note">↳ from any plot: soil profile · crop fit · amendments · weather advice · sustainability score · farm assistant (voice, en/hi/gu)</div>
    </div>
  </div>
</div>

<section id="modules">
  <div class="wrap">
    <div class="section-head">
      <span class="section-num">01</span>
      <h2>What's actually built</h2>
    </div>
    <p class="section-sub">Five modules, each answering one farmer question end-to-end — model in, API in the middle, a plain-language answer out.</p>

    <div class="modules">
      <div class="module-card">
        <div class="module-top">
          <div><div class="module-id">Core</div><div class="module-title">Crop-disease detection</div></div>
          <div class="stamp">Built</div>
        </div>
        <div class="module-desc">Photo of a leaf in, disease label out — with a Grad-CAM overlay showing where the model looked, and abstention when confidence is too low to trust.</div>
        <div class="module-path">model/ · POST /predict</div>
      </div>

      <div class="module-card">
        <div class="module-top">
          <div><div class="module-id">Module A</div><div class="module-title">Crop recommendation</div></div>
          <div class="stamp">Built</div>
        </div>
        <div class="module-desc">Re-imagined as GPS → real soil: SoilGrids 2.0 and the Soil Health Card resolve texture, pH and N-P-K for the exact plot, then suggest crop fit and amendments.</div>
        <div class="module-path">services/soil_* · routers/{soil,recommend}.py</div>
      </div>

      <div class="module-card">
        <div class="module-top">
          <div><div class="module-id">Module C</div><div class="module-title">Weather intelligence</div></div>
          <div class="stamp">Built</div>
        </div>
        <div class="module-desc">A 3-day Open-Meteo forecast runs through a rule engine and comes out the other side as something a farmer can act on today.</div>
        <div class="module-path">services/weather.py · POST /weather/advice</div>
      </div>

      <div class="module-card">
        <div class="module-top">
          <div><div class="module-id">Module D</div><div class="module-title">Sustainability score</div></div>
          <div class="stamp">Built</div>
        </div>
        <div class="module-desc">A reproducible, published formula scores each plot's practices and returns concrete tips to raise the score — no black box.</div>
        <div class="module-path">services/sustainability.py · POST /sustainability/score</div>
      </div>

      <div class="module-card">
        <div class="module-top">
          <div><div class="module-id">Module E</div><div class="module-title">GenAI farm assistant</div></div>
          <div class="stamp">Built</div>
        </div>
        <div class="module-desc">Grounded RAG over a disease-card corpus plus live plot context. Answers with Gemini when a key is set, or offline from the knowledge base when it isn't. Voice in and out, in English, Hindi and Gujarati.</div>
        <div class="module-path">services/assistant.py · POST /assistant/ask</div>
      </div>

      <div class="module-card dim">
        <div class="module-top">
          <div><div class="module-id">Modules F / G</div><div class="module-title">IoT / agentic advisor</div></div>
          <div class="stamp off">Not attempted</div>
        </div>
        <div class="module-desc">Scoped, planned, and deliberately left out of this build to keep the shipped modules solid.</div>
      </div>
    </div>
  </div>
</section>

<section id="metrics">
  <div class="wrap">
    <div class="section-head">
      <span class="section-num">02</span>
      <h2>How well the classifier actually holds up</h2>
    </div>
    <p class="section-sub"><strong style="color:var(--paper)">timm EfficientNet-B0</strong>, fine-tuned with field-simulation augmentation, temperature scaling, test-time augmentation, and low-confidence abstention — because a wrong diagnosis with high confidence is worse than an honest "not sure."</p>
    <div class="metrics">
      <div class="metric"><div class="num">0.966</div><div class="lbl">macro-F1 · 15% held-out validation</div></div>
      <div class="metric"><div class="num">0.967</div><div class="lbl">accuracy · same lab-image distribution</div></div>
      <div class="metric"><div class="num">0.992</div><div class="lbl">macro-F1 · predict-interface sanity check</div></div>
      <div class="metric"><div class="num">18</div><div class="lbl">disease classes, PlantVillage subset</div></div>
    </div>
    <p class="section-sub" style="margin-top:20px;">These are lab-image numbers. The real test is lab-to-field generalisation — the augmentation and abstention are built for exactly that gap, and the model retrains cleanly against the organisers' held-out field set when it ships.</p>
  </div>
</section>

<section id="data">
  <div class="wrap">
    <div class="section-head">
      <span class="section-num">03</span>
      <h2>Where the data lives</h2>
    </div>
    <p class="section-sub">The plan called for MongoDB. This build keeps that promise where it matters — accounts — and picks the simplest honest option everywhere else.</p>
    <div class="split">
      <div>
        <h4><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" style="color:var(--green)"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>MongoDB — accounts</h4>
        <p>Phone + OTP login, name, location, primary crop. Matches the original plan exactly, and it's visible in MongoDB Compass. Backed by a hand-rolled <code class="inline">motor</code> repo, not a full ODM — a handful of functions is enough, the same reasoning already used for JWT auth.</p>
        <span class="tag">app/backend/models/user.py · services/users.py</span>
      </div>
      <div>
        <h4><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" style="color:var(--amber)"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 4v16"/></svg>SQLite — farm data</h4>
        <p>Plots, plantings, diagnoses, irrigation, actions. One file, zero setup, so the farm-data side of the app runs straight from this project on any machine. The schema is a portable superset of the plan's original data model.</p>
        <span class="tag">app/backend/models/orm.py</span>
      </div>
    </div>
    <p class="section-sub" style="margin-top:18px;">Tests never touch a real MongoDB server — an in-memory <code class="inline">mongomock-motor</code> client stands in, so <code class="inline">pytest</code> runs clean with nothing installed.</p>
  </div>
</section>

<section id="architecture">
  <div class="wrap">
    <div class="section-head">
      <span class="section-num">04</span>
      <h2>How a request travels</h2>
    </div>
    <p class="section-sub">One API, one auth layer, five places it can go depending on what the farmer asked.</p>

    <div class="arch">
      <div class="arch-box accent">React + Vite + Tailwind SPA · en / hi / gu</div>
      <div class="arch-connector"></div>
      <div class="arch-box accent">FastAPI · JWT auth</div>
      <div class="arch-connector"></div>
      <div class="arch-branches">
        <div class="arch-box">SQLite (async)<br>plots · diagnoses · logs</div>
        <div class="arch-box">MongoDB (motor)<br>accounts</div>
        <div class="arch-box">EfficientNet-B0<br>+ Grad-CAM + abstain</div>
        <div class="arch-box">SoilGrids 2.0<br>+ Soil Health Card</div>
        <div class="arch-box">Open-Meteo<br>→ rule engine</div>
        <div class="arch-box">Sustainability<br>formula</div>
        <div class="arch-box">disease_cards.json<br>→ Gemini / offline</div>
      </div>
    </div>
    <p class="section-sub" style="margin-top:20px;">Every route lives under <code class="inline">/api</code> — the SPA keeps bare paths like <code class="inline">/weather</code> and <code class="inline">/soil</code> for itself. Uploaded images and Grad-CAM overlays serve from <code class="inline">/uploads</code>.</p>

    <div style="margin-top:36px; overflow-x:auto;">
      <table class="ledger">
        <tr><th>Method</th><th>Endpoint</th><th>Auth</th><th>Purpose</th></tr>
        <tr><td class="method">POST</td><td class="endpoint">/api/auth/otp/*, /api/auth/guest</td><td class="auth">–</td><td>phone + OTP login, guest, onboarding</td></tr>
        <tr><td class="method">GET</td><td class="endpoint">/api/auth/me</td><td class="auth">required</td><td>current account</td></tr>
        <tr><td class="method">CRUD</td><td class="endpoint">/api/plots, /api/plots/{id}</td><td class="auth">required</td><td>fields — create auto-fetches soil</td></tr>
        <tr><td class="method">GET</td><td class="endpoint">/api/plots/{id}/timeline</td><td class="auth">required</td><td>merged diagnoses + irrigation + actions</td></tr>
        <tr><td class="method">POST</td><td class="endpoint">/api/predict</td><td class="auth">required</td><td>disease diagnosis + Grad-CAM, writes history</td></tr>
        <tr><td class="method">POST</td><td class="endpoint">/api/soil/lookup, /api/recommend/*</td><td class="auth">–</td><td>soil profile → crop fit → amendments</td></tr>
        <tr><td class="method">POST</td><td class="endpoint">/api/weather/advice</td><td class="auth">–</td><td>3-day forecast → farmer actions</td></tr>
        <tr><td class="method">POST</td><td class="endpoint">/api/sustainability/score</td><td class="auth">–</td><td>score + tips</td></tr>
        <tr><td class="method">POST</td><td class="endpoint">/api/assistant/ask</td><td class="auth">optional</td><td>grounded RAG, voice, en/hi/gu</td></tr>
      </table>
    </div>
  </div>
</section>

<section id="sources">
  <div class="wrap">
    <div class="section-head">
      <span class="section-num">05</span>
      <h2>Where the numbers come from</h2>
    </div>
    <p class="section-sub">Nothing here is invented — every figure the app shows a farmer traces back to a named, licensed source.</p>
    <div class="sources">
      <div class="source-row"><span class="src-name">PlantVillage</span><span class="src-use">training the 18-class disease classifier</span><span class="src-lic">CC0</span></div>
      <div class="source-row"><span class="src-name">SoilGrids 2.0 (ISRIC)</span><span class="src-use">texture, pH, SOC, N, CEC, bulk density</span><span class="src-lic">CC-BY 4.0</span></div>
      <div class="source-row"><span class="src-name">Soil Health Card</span><span class="src-use">district-average available N / P / K</span><span class="src-lic">Govt. of India open data</span></div>
      <div class="source-row"><span class="src-name">Open-Meteo</span><span class="src-use">3-day weather forecast</span><span class="src-lic">CC-BY 4.0</span></div>
      <div class="source-row"><span class="src-name">Nominatim / OSM</span><span class="src-use">reverse geocoding, map tiles</span><span class="src-lic">ODbL</span></div>
      <div class="source-row"><span class="src-name">Google Gemini</span><span class="src-use">assistant answers, when a key is set</span><span class="src-lic">Google API terms</span></div>
      <div class="source-row"><span class="src-name">ICAR / State Ag-Univ</span><span class="src-use">crop, amendment and disease-card thresholds</span><span class="src-lic">package of practices</span></div>
    </div>
  </div>
</section>

<section id="stack">
  <div class="wrap">
    <div class="section-head">
      <span class="section-num">06</span>
      <h2>Built with</h2>
    </div>
    <div class="stack-group">
      <h4>Backend</h4>
      <div class="chips"><span class="chip">FastAPI</span><span class="chip">SQLAlchemy 2 (async)</span><span class="chip">Motor</span><span class="chip">PyJWT</span><span class="chip">httpx</span><span class="chip">Pydantic v2</span></div>
    </div>
    <div class="stack-group">
      <h4>Machine learning</h4>
      <div class="chips"><span class="chip">PyTorch</span><span class="chip">timm (EfficientNet-B0)</span><span class="chip">torchvision</span><span class="chip">pytorch-grad-cam</span><span class="chip">scikit-learn</span><span class="chip">Pillow</span></div>
    </div>
    <div class="stack-group">
      <h4>Frontend</h4>
      <div class="chips"><span class="chip">React 19</span><span class="chip">Vite 6</span><span class="chip">Tailwind CSS v4</span><span class="chip">react-router-dom</span><span class="chip">react-leaflet</span><span class="chip">clsx</span></div>
    </div>
    <div class="stack-group">
      <h4>Assistant</h4>
      <div class="chips"><span class="chip">google-generativeai</span><span class="chip">Web Speech API</span></div>
    </div>
  </div>
</section>

<section id="layout">
  <div class="wrap">
    <div class="section-head">
      <span class="section-num">07</span>
      <h2>Repository layout</h2>
    </div>
    <div class="tree">
<span class="folder">app/backend/</span>  <span class="desc">FastAPI: auth, db (SQLite), mongo (accounts), models/, routers/, services/</span>
<span class="folder">app/frontend/</span> <span class="desc">React SPA: pages/, components/, auth/, i18n/, lib/</span>
<span class="folder">model/</span>         <span class="desc">download_data · dataset · net · train · predict · evaluate · gradcam · infer · labels</span>
<span class="folder">data/</span>          <span class="desc">disease_cards.json · crop_suitability.json · soil_amendments.json · shc_reference/ · samples/</span>
<span class="folder">docs/</span>          <span class="desc">soil_sources · weather_rules · sustainability</span>
<span class="folder">report/</span>        <span class="desc">model_report.md (generated)</span>
<span class="folder">tests/</span>         <span class="desc">47 tests (pytest)</span>
    </div>
  </div>
</section>

<footer>
  <div class="wrap">
    <div class="field-note">
      <h3>Originality declaration</h3>
      <ul>
        <li>All application, ML-pipeline and frontend code is original work for this hackathon.</li>
        <li>Reused, unmodified, via public interfaces: PlantVillage images, the SoilGrids 2.0 REST API, Soil Health Card published averages, Open-Meteo, Nominatim / OpenStreetMap, a pretrained EfficientNet-B0 backbone (timm, ImageNet), and the open-source libraries listed above.</li>
        <li>No public notebook or solution was copied. AI coding assistants were used during development — the working system and its evaluation are what's submitted.</li>
      </ul>
      <div class="foot-meta">
        <span>AgriSmart AI · SIH 2026 · PS-1 / C-433</span>
        <span>pytest -q → 47 passed · npm run build → clean</span>
      </div>
    </div>
  </div>
</footer>

</body>
</html>
