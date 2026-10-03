// A big sample workspace shared by the three workspace-scale prototypes.
// It grows the seed workspace (anchor/seed.py) to six sub-questions, about 20
// sources, and around 250 blocks, so the hard part shows: too many blocks to
// hold in your head. Nothing here talks to the real core.
(function () {
  "use strict";

  const PEOPLE = {
    Sam: { role: "Researcher", sme: true }, Dana: { role: "Data science lead", sme: true },
    Lee: { role: "Research lead", sme: false }, Priya: { role: "Analytics", sme: false }, Jordan: { role: "Product manager", sme: false },
  };
  const YOU = "Sam";

  const LEVEL = { source: "Source", observation: "Observation", finding: "Finding", insight: "Insight", decision: "Decision" };
  const STATE = {
    needs_check: "Needs a check", checked_by_owner: "Checked by owner", checked_by_peers: "Checked by peers",
    checked_by_sme: "Checked by an SME", needs_changes: "Needs changes", disagreement: "Disagree",
    retired: "Retired",
  };
  const VERDICT = { looks_right: "Looks right", needs_changes: "Needs changes", disagree: "Disagree" };
  const HOW = { evidence: "Read the evidence", source_data: "Checked the source data", reran: "Reran the numbers", judgment: "Used my judgment" };
  const ASKS = {
    observation: ["Does the source say exactly this, no more and no less?", "If there is a number, does it match the source?"],
    finding: ["Do the blocks under it really add up to this?", "Would a skeptic read them the same way?", "Is anything under it still unchecked?"],
    insight: ["Does it follow from the findings under it?", "Does it say why this matters to our goal?", "What would make it wrong?"],
  };

  // Sub-questions. Each one has its sources, observations, findings and insights.
  // In findings and insights, "on" points at observations or findings in the same
  // sub-question by index (o3, f1), or in another one (q2.f0).
  const QS = [
    {
      key: "q1", text: "Which checkout step loses the most people on a phone?", short: "Where people leave",
      sources: [
        ["query", "Checkout funnel, last 30 days", "Priya", "Mobile web, Aug 29 to Sep 27.\nCart 12,000\nStarted address form 10,900\nFinished address form 6,650\nReached payment 5,600\nPaid 5,040 (42%)"],
        ["note", "Session replays, 40 mobile checkouts", "Jordan", "12 replays: keyboard covers the next field.\n7 replays: scroll up to fix a typo in the street line.\nZip field takes 2 or 3 taps before it takes input."],
        ["data", "Step timing by device", "Priya", "Address step median: phone 94s, laptop 41s.\nDesktop conversion 68%.\nAndroid address drop-off 41%, iPhone 37%."],
      ],
      obs: [
        ["Mobile checkout conversion is 42 percent", 0],
        ["39 percent of shoppers who start the address form leave before finishing it", 0],
        ["16 percent of shoppers who reach payment leave before paying", 0],
        ["9 percent leave on the cart page before starting checkout", 0],
        ["Median time on the address step is 94 seconds on a phone and 41 on a laptop", 2],
        ["Shoppers tap the zip field 2 or 3 times before it takes input", 1],
        ["12 of 40 replays show the keyboard covering the next field", 1],
        ["Desktop checkout conversion is 68 percent", 2],
        ["7 of 40 replays show shoppers scrolling up to fix a typo", 1],
        ["Error messages show off screen on 6 of 9 address fields", 1],
        ["Android shoppers leave the address step a bit more than iPhone shoppers, 41 vs 37 percent", 2],
      ],
      finds: [
        ["The address step loses more mobile shoppers than any other step", ["o1", "o2", "o3", "o0"]],
        ["Phone keyboards make the address form slower and more error prone", ["o4", "o5", "o6", "o8"]],
        ["Hidden error messages make shoppers fix the same field twice", ["o8", "o9"]],
        ["Payment step loss is normal for our category", ["o2"]],
        ["Most shoppers prefer a one page checkout", []],
      ],
      ins: [
        ["Address entry is the biggest fixable cause of mobile checkout drop-off for us", ["f0", "f1", "q2.f0"]],
      ],
      extra: ["said the zip field jumped when the keyboard opened", "gave up at the street line", "typed the address twice after an error",
        "said the form felt longer than on a laptop", "missed the apartment field", "said the form cleared after switching apps"],
    },
    {
      key: "q2", text: "Would not typing an address change whether shoppers pay?", short: "Skip the typing",
      sources: [
        ["data", "Returning vs new shoppers", "Priya", "Returning: 31% of mobile checkouts, 61% pay.\nNew: 69% of mobile checkouts, 34% pay.\nSaved address skips the address step."],
        ["note", "Interviews, shoppers 1 to 8", "Sam", "S1: \"Typing my whole address with my thumbs, no thanks.\"\nS2: \"The keyboard kept covering the zip field.\"\nS5: \"Address was fine, I have it saved.\"\nS8: \"Typing it out is a pain.\""],
        ["query", "Autofill pilot, Canada, 3 weeks", "Dana", "4,100 mobile shoppers.\nAddress step time 88s to 31s.\nMobile conversion 40% to 47%.\nWrong apartment picked in 4% of orders."],
        ["note", "Competitor teardown", "Jordan", "3 of 5 competitors offer address lookup on mobile.\n2 of 5 show a map pin."],
      ],
      obs: [
        ["Returning shoppers pay 61 percent of the time, new shoppers 34 percent", 0],
        ["Returning shoppers with a saved address skip the address step", 0],
        ["6 of 8 shoppers said typing an address on a phone is tedious", 1],
        ["2 shoppers said the keyboard covered or moved the form fields", 1],
        ["In the Canada pilot, autofill cut address step time from 88 to 31 seconds", 2],
        ["In the Canada pilot, mobile conversion rose from 40 to 47 percent", 2],
        ["The Canada pilot ran for 3 weeks with 4,100 shoppers", 2],
        ["3 of 5 competitors offer address lookup on mobile", 3],
        ["Address lookup picked the wrong apartment in 4 percent of pilot orders", 2],
        ["1 shopper said she does not trust autofill with her home address", 1],
        ["Saved address shoppers are mostly repeat buyers", 0],
      ],
      finds: [
        ["Not having to type an address roughly doubles the chance a shopper pays", ["o0", "o1"]],
        ["Autofill cut the time and raised conversion in the pilot", ["o4", "o5", "o6"]],
        ["Shoppers find typing an address on a phone tedious", ["o2", "o3"]],
        ["Saved address shoppers are also more loyal, so the gap overstates the effect", ["o0", "o1", "o10"]],
        ["Address lookup errors are small but real", ["o8", "o9"]],
      ],
      ins: [
        ["Autofill is likely to lift mobile conversion by a few points, not double it", ["f1", "f3"]],
        ["Returning shoppers are where an address fix will be easiest to measure", ["f0"]],
      ],
      extra: ["said a saved address is the only reason they finish on a phone", "asked why the site does not remember the address",
        "said they would accept a map pin", "worried lookup would pick the wrong flat", "copied the address from another app"],
    },
    {
      key: "q3", text: "Do other payment options matter as much as the address form?", short: "Payment options",
      sources: [
        ["note", "Interviews, shoppers 5 to 8", "Sam", "S6: \"The form is long on a phone.\"\nS7: \"I would have used Apple Pay if it was there.\""],
        ["data", "Payment method mix, mobile", "Priya", "Card 74%. PayPal 18%. Gift card 8%.\nCard number errors in 8% of attempts.\n64% of payment exits after card form loads."],
        ["data", "Shopper survey, 1,200 people", "Lee", "22% pay with a wallet app on a phone.\nWallet users finish 1.4x as often.\nTop annoyance: too many fields 31%, no wallet 12%, surprise costs 18%."],
      ],
      obs: [
        ["1 shopper said she would pay with Apple Pay if offered", 0],
        ["22 percent of survey respondents use a wallet app to pay on a phone", 2],
        ["Wallet users finish checkout 1.4 times as often in the survey", 2],
        ["64 percent of payment step exits happen after the card form loads", 1],
        ["Card number errors happen in 8 percent of mobile payment attempts", 1],
        ["31 percent of respondents rank too many fields as the top annoyance", 2],
        ["12 percent of respondents rank no wallet option as the top annoyance", 2],
        ["PayPal is 18 percent of mobile payments today", 1],
        ["Respondents under 30 use wallets twice as often as those over 50", 2],
      ],
      finds: [
        ["Adding Apple Pay would fix most mobile checkout drop-off", ["o0"]],
        ["Wallets help, but fewer shoppers care about them than about form length", ["o1", "o2", "o5", "o6"]],
        ["Card entry is a second, smaller form problem", ["o3", "o4"]],
      ],
      ins: [
        ["A wallet option is a smaller win than address autofill for our shoppers", ["f1", "q1.f0"]],
        ["Younger shoppers may close more of the gap with wallets", ["f1"]],
      ],
      extra: ["asked for Google Pay", "said they keep their card in the browser", "gave up when the card form reloaded",
        "said PayPal feels safer on a phone", "did not see the wallet button"],
    },
    {
      key: "q4", text: "How many mobile shoppers finish checkout on a laptop instead?", short: "Moved to laptop",
      sources: [
        ["query", "Cross-device sessions, Q2", "Dana", "Mobile checkouts left: 18,400.\nSame account paid on a laptop within 24h: 4,700 (26%).\nOnly signed in shoppers can be matched (48%)."],
        ["note", "Interviews, shoppers 1 to 4", "Sam", "S3: \"I gave up and finished on my laptop.\""],
      ],
      obs: [
        ["26 percent of shoppers who leave mobile checkout pay on a laptop within a day", 0],
        ["1 shopper said she gave up and finished on her laptop", 1],
        ["Cross-device matching only works for signed in shoppers, 48 percent of traffic", 0],
        ["Shoppers who switch devices have carts 1.6 times larger", 0],
        ["40 percent of switchers switch the same evening", 0],
      ],
      finds: [
        ["About a quarter of mobile drop-off is moved, not lost", ["o0", "o2"]],
        ["Bigger carts are more likely to move to a laptop", ["o3", "o4"]],
      ],
      ins: [
        ["Part of the mobile gap is a measuring gap, so lost sales are lower than the funnel says", ["f0"]],
      ],
      extra: ["said they save big orders for the laptop", "emailed the cart to themselves", "finished on a tablet"],
    },
    {
      key: "q5", text: "Do delivery costs shown late drive people away?", short: "Late delivery costs",
      sources: [
        ["query", "Delivery cost test, A/B", "Dana", "Show cost in cart vs on payment.\nPayment exits down 3 points in the cart variant."],
        ["note", "Support tickets, September", "Jordan", "140 tickets mention delivery cost.\nMost ask why the price changed at the end."],
        ["data", "Cart sizes, mobile", "Priya", "Free delivery from $50.\nMedian mobile cart $43.\n9% of carts add an item to reach free delivery."],
      ],
      obs: [
        ["Delivery cost first shows on the payment step on mobile", 0],
        ["Showing delivery cost in the cart cut payment step exits by 3 points", 0],
        ["18 percent of survey respondents name surprise costs as a reason to leave", 0],
        ["140 support tickets last month mention delivery cost", 1],
        ["The free delivery threshold is $50 and the median mobile cart is $43", 2],
        ["9 percent of carts add an item to reach free delivery", 2],
      ],
      finds: [
        ["Showing delivery cost late adds to payment step drop-off", ["o0", "o1", "o2"]],
        ["The free delivery threshold sits just above most mobile carts", ["o4", "o5"]],
        ["Support tickets show cost confusion is common", ["o3"]],
        ["Shoppers expect free delivery everywhere", []],
      ],
      ins: [
        ["Late delivery costs are a second, cheaper fix we could ship before autofill", ["f0", "f1"]],
      ],
      extra: ["said the total jumped at the end", "removed an item after seeing delivery", "asked for a delivery estimate in the cart"],
    },
    {
      key: "q6", text: "Does page speed on slow networks matter?", short: "Slow networks",
      sources: [
        ["query", "Speed by network type", "Priya", "Address page: wifi 1.8s, 3G 5.2s.\n3G shoppers leave the address step 9 points more.\n11% of mobile checkouts on 3G or slower."],
        ["data", "Field data, address page", "Dana", "Script size 1.1 MB.\nPilot lookup adds 400ms per keystroke on 3G."],
      ],
      obs: [
        ["The address page loads in 1.8 seconds on wifi and 5.2 on 3G", 0],
        ["Shoppers on 3G leave the address step 9 points more often", 0],
        ["11 percent of mobile checkouts happen on 3G or slower", 0],
        ["The address page ships 1.1 MB of script", 1],
        ["Lookup calls add 400 ms per keystroke on 3G in the pilot", 1],
      ],
      finds: [
        ["Slow networks make the address step worse for a small group", ["o0", "o1", "o2"]],
        ["Address lookup could be slow on bad networks", ["o4"]],
      ],
      ins: [
        ["Autofill must work on slow networks or it misses the shoppers who struggle most", ["f0", "f1"]],
      ],
      extra: ["said the page froze on the train", "tapped submit twice on a slow connection", "waited for the lookup and gave up"],
    },
  ];

  const DECISION = { text: "Fund address autofill in Q3", insights: ["q1.i0", "q2.i0", "q3.i0", "q4.i0", "q5.i0", "q6.i0"] };

  // Hand-set states for the blocks the story turns on. Key: "q1.f3" etc.
  const FIXED = {
    "q1.o0": ["Priya", false, [["Sam", "looks_right", "source_data"]]],
    "q1.f0": ["Jordan", true, [["Jordan"], ["Sam", "looks_right", "evidence"], ["Dana", "looks_right", "reran"]]],
    "q1.f2": ["Jordan", true, [["Jordan"], ["Lee", "needs_changes", null, "Only 6 of 9 fields. Say which ones."]]],
    "q1.f3": ["Jordan", true, [["Jordan"], ["Dana", "disagree", null, "We have no category benchmark in the sources."]]],
    "q1.i0": ["Jordan", false, [["Sam", "looks_right", "judgment", "Strong. Check the open observations before the pitch."]]],
    "q2.o3": ["Jordan", true, []],
    "q2.f0": ["Priya", false, [["Lee", "looks_right", "evidence"]]],
    "q2.f3": ["Sam", true, []],
    "q2.i0": ["Sam", true, []],
    "q2.i1": ["Priya", true, []],
    "q3.o0": ["Jordan", true, [["Jordan"], ["Lee", "needs_changes", null, "Only S7 said this. It is 1 shopper, not 2."]]],
    "q3.f0": ["Jordan", true, [["Jordan"], ["Dana", "disagree", null, "One quote cannot carry this. The funnel says the loss is at the address step."]]],
    "q3.i1": ["Priya", true, []],
    "q4.o0": ["Priya", false, [["Dana", "looks_right", "reran"]]],
    "q4.o2": ["Priya", false, [["Dana", "looks_right", "source_data"]]],
    "q4.f0": ["Dana", false, [["Sam", "looks_right", "evidence"]]],
    "q4.i0": ["Dana", false, [["Lee", "looks_right", "judgment"]]],
    "q5.f2": ["Sam", true, []],
    "q6.i0": ["Jordan", true, [["Jordan"]]],
  };

  const WHY = {
    high: ["Read straight from the source", "Worked out from the numbers in the source", "The source says it in so many words"],
    medium: ["Two sources point the same way", "Read from the notes, with some judgment", "Inferred from a pattern in the data"],
    low: ["One quote says it", "Common in other studies", "A guess from a small sample"],
  };
  const ASSUMES = [
    "The people we talked to are like most mobile shoppers", "The last 30 days were a normal month",
    "The pilot shoppers are like our shoppers", "Signed in shoppers behave like everyone else",
    "Survey answers match what people do",
  ];

  // Small seeded random, so every load is the same.
  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

  function build(size) {
    const big = size !== "small";
    const r = rng(47);
    const pick = a => a[Math.floor(r() * a.length)];
    const cast = Object.keys(PEOPLE);
    const blocks = [], sources = [], byKey = {};
    let n = 0;

    function randomChecks(owner, ai) {
      const x = r();
      const others = cast.filter(p => p !== owner);
      const ownerCk = ai ? [[owner]] : [];
      if (x < 0.30) return ai && r() < 0.5 ? [] : ownerCk;                    // needs a check, or owner only
      if (x < 0.62) return [...ownerCk, [pick(others.filter(p => !PEOPLE[p].sme)), "looks_right", pick(Object.keys(HOW))]];
      if (x < 0.95) return [...ownerCk, [pick(others.filter(p => PEOPLE[p].sme)), "looks_right", pick(Object.keys(HOW))]];
      if (x < 0.98) return [...ownerCk, [pick(others), "needs_changes", null, "Say where this number comes from."]];
      return [...ownerCk, [pick(others), "disagree", null, "The source does not say this."]];
    }

    function add(key, level, q, text, extra) {
      n += 1;
      const fixed = FIXED[key];
      const owner = fixed ? fixed[0] : pick(cast);
      const ai = fixed ? fixed[1] : extra && extra.ai !== undefined ? extra.ai : r() < (level === "observation" ? 0.55 : 0.45);
      const conf = ai ? (r() < 0.45 ? "high" : r() < 0.7 ? "medium" : "low") : null;
      const checks = (fixed ? fixed[2] : randomChecks(owner, ai)).map(([by, verdict = "looks_right", how = null, note = ""]) => ({ by, verdict, how, note }));
      const b = Object.assign({
        id: "b" + n, n, key, level, q, text, owner, ai, conf,
        why: ai ? pick(WHY[conf]) : null, assumes: ai && r() < 0.6 ? [pick(ASSUMES)] : [],
        on: [], src: [], checks,
      }, extra);
      blocks.push(b); byKey[key] = b;
      return b;
    }

    QS.forEach((q, qi) => {
      q.sources.forEach(([kind, title, by, body], si) => {
        const s = { id: `s${qi}_${si}`, key: `${q.key}.s${si}`, level: "source", q: q.key, kind, title, by, body, text: title };
        sources.push(s); byKey[s.key] = s;
      });
      q.obs.forEach(([text, si], oi) => add(`${q.key}.o${oi}`, "observation", q.key, text, { src: [`s${qi}_${si}`] }));
      // Many more observations, the way a big interview round or an AI breakdown adds them.
      if (big) {
        const interviews = q.sources.findIndex(s => s[0] === "note");
        const count = 20 + Math.floor(r() * 14);
        for (let i = 0; i < count; i++) {
          const who = `P${10 + qi * 30 + i}`;
          add(`${q.key}.x${i}`, "observation", q.key, `Shopper ${who} ${pick(q.extra)}`, { src: [`s${qi}_${Math.max(0, interviews)}`] });
        }
      }
    });
    // Findings and insights, after every observation exists so links can cross sub-questions.
    const resolve = (q, ref) => byKey[ref.includes(".") ? ref : `${q.key}.${ref}`];
    QS.forEach(q => q.finds.forEach(([text, on], fi) => {
      const b = add(`${q.key}.f${fi}`, "finding", q.key, text, {});
      b.on = on.map(ref => resolve(q, ref).id);
      if (big && on.length && q.key !== "q4") {   // findings also lean on some of the extra observations
        const xs = blocks.filter(x => x.q === q.key && x.key.includes(".x"));
        for (let i = 0; i < 2 + Math.floor(r() * 4); i++) { const x = pick(xs); if (x && !b.on.includes(x.id)) b.on.push(x.id); }
      }
    }));
    if (big) {   // a second wave of AI findings, built on the interview round
      QS.forEach(q => {
        const xs = blocks.filter(x => x.q === q.key && x.key.includes(".x"));
        const per = q.key === "q4" || q.key === "q6" ? 1 : 3;
        for (let i = 0; i < per; i++) {
          const a = pick(xs), c = pick(xs);
          const b = add(`${q.key}.w${i}`, "finding", q.key, `Several shoppers ${a.text.replace(/^Shopper P\d+ /, "")}`, { ai: true });
          b.ai = true; b.conf = "medium"; b.why = "Several interview notes say something like it";
          b.on = [...new Set([a.id, c.id])];
        }
      });
    }
    QS.forEach(q => q.ins.forEach(([text, on], ii) => {
      const b = add(`${q.key}.i${ii}`, "insight", q.key, text, {});
      b.on = on.map(ref => resolve(q, ref).id);
    }));

    const questions = QS.map((q, i) => ({ id: q.key, n: i + 1, text: q.text, short: q.short }));
    const decision = { id: "D", level: "decision", text: DECISION.text, on: DECISION.insights.map(k => byKey[k].id), q: null };
    return new Workspace({
      question: "Why do mobile shoppers leave checkout before paying?",
      decisionText: "Whether to fund address autofill in Q3",
      questions, sources, blocks, decision,
    });
  }

  // ---------- The rules (docs/GLOSSARY.md), worked out the same way the core does ----------
  class Workspace {
    constructor(d) {
      Object.assign(this, d);
      this.you = YOU;
      this.conflicts = d.conflicts || [];   // {id, a, b, confirmed, by, note, status: open|waiting|settled, outcome}
      this.people = PEOPLE;
      this.index = new Map();
      [...this.sources, ...this.blocks, this.decision].forEach(x => this.index.set(x.id, x));
      this.relink();
    }
    // Who is built on whom. Called again after anything moves.
    relink() {
      this.above = new Map();     // id -> blocks built on it
      this.index.forEach(x => this.above.set(x.id, []));
      [...this.blocks, this.decision].forEach(b => {
        (b.on || []).forEach(id => this.above.get(id).push(b.id));
        (b.src || []).forEach(id => this.above.get(id).push(b.id));
      });
    }
    get(id) { return this.index.get(id); }
    under(id) { const b = this.get(id); return [...(b.on || []), ...(b.src || [])]; }
    over(id) { return this.above.get(id) || []; }
    // Checks on the current wording only. Checks on an earlier version stay in history.
    latest(b) { const m = new Map(); b.checks.filter(c => !c.old).forEach(c => m.set(c.by, c)); return [...m.values()]; }
    state(b) {
      if (b.level === "source") return "source";
      if (b.level === "decision") return "decision";
      if (b.retired) return "retired";
      if (this.conflictsOf(b).some(c => c.confirmed)) return "disagreement";
      const cs = this.latest(b);
      if (cs.some(c => c.verdict === "disagree")) return "disagreement";
      if (cs.some(c => c.verdict === "needs_changes")) return "needs_changes";
      const ok = cs.filter(c => c.verdict === "looks_right" && c.by !== b.owner);
      if (ok.some(c => PEOPLE[c.by] && PEOPLE[c.by].sme)) return "checked_by_sme";
      if (ok.length) return "checked_by_peers";
      if (cs.some(c => c.by === b.owner)) return "checked_by_owner";
      return "needs_check";
    }
    unchecked(b) { const s = this.state(b); return s === "needs_check" || s === "needs_changes" || s === "disagreement" || s === "retired"; }
    trouble(b) { const s = this.state(b); return s === "needs_changes" || s === "disagreement" || this.restsOnNothing(b); }
    restsOnNothing(b) { return (b.level === "finding" || b.level === "insight") && !(b.on || []).length; }
    // Blocks under it, all the way down, that still need a check: the ⚠.
    weakBelow(b, seen = new Set()) {
      const out = [];
      (b.on || []).forEach(id => {
        if (seen.has(id)) return; seen.add(id);
        const c = this.get(id);
        if (this.unchecked(c)) out.push(c);
        out.push(...this.weakBelow(c, seen));
      });
      return out;
    }
    glow(b) { return b.level === "insight" && this.latest(b).some(c => c.verdict === "looks_right" && c.by !== b.owner); }
    // What waits on you, and why.
    waits(b, me = this.you) {
      if (b.level === "source" || b.level === "decision") return null;
      const s = this.state(b);
      const mine = this.latest(b).find(c => c.by === me);
      if (b.owner === me) {
        if (b.ai && !mine) return "Your AI draft";
        if (s === "needs_changes" || s === "disagreement") return "Changes asked";
        return null;
      }
      if (b.ai && !this.latest(b).some(c => c.by === b.owner)) return null;   // waits on its owner first
      if (mine) return null;
      if (s === "needs_check" || s === "checked_by_owner") return "Nobody else has checked it";
      return null;
    }
    waitingOn(b) {
      if (b.ai && !this.latest(b).some(c => c.by === b.owner)) return b.owner;
      return null;
    }
    // Everything upstream and downstream: the line of a block.
    lineage(id) {
      const set = new Set([id]);
      const down = x => this.under(x).forEach(y => { if (!set.has(y)) { set.add(y); down(y); } });
      const up = x => this.over(x).forEach(y => { if (!set.has(y)) { set.add(y); up(y); } });
      down(id); up(id);
      return set;
    }
    // How many blocks above this one would lose a ⚠ if it were checked.
    unlocks(b) {
      const seen = new Set(); let count = 0;
      const up = x => this.over(x).forEach(y => {
        if (seen.has(y)) return; seen.add(y);
        const c = this.get(y);
        if (c.level !== "decision") {
          const weak = this.weakBelow(c).filter(w => w.id !== b.id);
          if (!weak.length) count += 1;
        }
        up(y);
      });
      up(b.id);
      return count;
    }
    check(b, by, verdict, how = null, note = "") { b.checks.push({ by, verdict, how, note, fresh: true }); }

    // ---------- Conflicts, versions, retiring ----------
    conflictsOf(b, all = false) { return this.conflicts.filter(c => (c.a === b.id || c.b === b.id) && (all || c.status !== "settled")); }
    // A new version of the wording. Earlier checks move to history and checkers are asked to look again.
    revise(b, text, by, note = "") {
      b.versions = b.versions || [];
      b.versions.push({ text: b.text, by, note });
      b.checks.forEach(c => { c.old = true; });
      b.text = text;
      b.checks.push({ by: b.owner, verdict: "looks_right", how: null, note: note || "New version", fresh: true });
    }
    // Retire: out of the way, never erased. What was built on it is flagged, or moved onto its replacement.
    retire(b, by, reason, other = null, move = false) {
      b.retired = { by, reason, other };
      if (other && move) {
        this.over(b.id).forEach(id => { const x = this.get(id); x.on = x.on.map(y => y === b.id ? other : y).filter((y, i, a) => a.indexOf(y) === i); });
        this.relink();
      }
    }
    unretire(b) { delete b.retired; }
    // Delete is only for a mistake: yours, unchecked by anyone else, nothing built on it, no conflict.
    canDelete(b, me = this.you) {
      return b.owner === me && !this.latest(b).some(c => c.by !== me) && !this.over(b.id).length && !this.conflictsOf(b, true).length;
    }
    remove(b) {
      this.blocks = this.blocks.filter(x => x !== b);
      this.index.delete(b.id);
      this.relink();
    }
    restsOnRetired(b) { return (b.on || []).some(id => this.get(id).retired); }
    live() { return this.blocks.filter(b => !b.retired); }
    questionState(qid) {
      const ins = this.blocks.filter(b => b.q === qid && b.level === "insight");
      if (ins.some(b => this.glow(b) && !this.weakBelow(b).length)) return "Answered";
      if (this.blocks.some(b => b.q === qid && (b.level === "finding" || b.level === "insight"))) return "In progress";
      return "Open";
    }
    counts(list = this.blocks) {
      const c = { total: list.length, waits: 0, trouble: 0, unchecked: 0, checked: 0 };
      list.forEach(b => {
        if (this.waits(b)) c.waits += 1;
        if (this.trouble(b)) c.trouble += 1;
        if (this.unchecked(b)) c.unchecked += 1; else c.checked += 1;
      });
      return c;
    }
    label(b) {
      if (b.level === "source") return `Source · ${b.kind}`;
      if (b.level === "decision") return "Decision";
      return `${LEVEL[b.level]} #${b.n}`;
    }
  }

  // ---------- Shared bits of UI: the marks and the detail with the check ----------
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function shape(level) { return `<span class="shape ${level}" aria-hidden="true"></span>`; }
  function aiTag(b) { return b.ai ? `<span class="ai" title="Made with AI">AI</span>` : ""; }
  // Only trouble gets words. With onlyExtra, leave out what the state tag already says.
  function troubleTags(ws, b, onlyExtra = false) {
    const s = ws.state(b), t = [];
    if (!onlyExtra && s === "needs_changes") t.push(`<span class="tag t-needs_changes">Needs changes</span>`);
    if (!onlyExtra && s === "disagreement") t.push(`<span class="tag t-disagreement">Disagree</span>`);
    if (ws.restsOnNothing(b)) t.push(`<span class="tag t-nothing">Rests on nothing</span>`);
    if (!t.length && ws.weakBelow(b).length) t.push(`<span class="warn" title="Built on blocks that still need a check">⚠</span>`);
    return t.join("");
  }
  function stateTag(ws, b) {
    const s = ws.state(b);
    if (s === "source" || s === "decision") return "";
    return `<span class="tag t-${s}"><span class="sq s-${s}"></span>${STATE[s]}</span>`;
  }

  // The detail of one block, with the check at the bottom. The host page wires
  // clicks: [data-go] moves to another block, [data-v] picks a verdict,
  // [data-how] picks how, [data-save] saves the check.
  function detail(ws, id, opts = {}) {
    const b = ws.get(id);
    if (!b) return "";
    const me = ws.you;
    if (b.level === "source") {
      const over = ws.over(id).map(x => ws.get(x));
      return `<div class="dt">
        <div class="eyebrow"><span class="shape source"></span>${esc(ws.label(b))} · added by ${esc(b.by)}</div>
        <h2>${esc(b.title)}</h2>
        <pre class="srcbody">${esc(b.body)}</pre>
        <div class="sect"><h3>Taken from it (${over.length})</h3>${over.map(x => item(ws, x)).join("")}</div>
      </div>`;
    }
    if (b.level === "decision") {
      const ins = b.on.map(x => ws.get(x));
      const ready = ins.filter(x => !ws.unchecked(x) && !ws.weakBelow(x).length).length;
      return `<div class="dt">
        <div class="eyebrow"><span class="shape decision"></span>Decision</div>
        <h2>${esc(b.text)}</h2>
        <p class="muted small">${ready} of ${ins.length} insights it relies on stand on checked ground all the way down.</p>
        <div class="sect"><h3>Relies on</h3>${ins.map(x => item(ws, x)).join("")}</div>
      </div>`;
    }
    const s = ws.state(b);
    const under = b.on.map(x => ws.get(x));
    const srcs = b.src.map(x => ws.get(x));
    const over = ws.over(id).map(x => ws.get(x));
    const weak = ws.weakBelow(b);
    const q = ws.questions.find(x => x.id === b.q);
    const why = ws.waits(b);
    const waitingOn = ws.waitingOn(b);
    const hist = ws.latest(b);
    const pend = opts.pending || {};
    let check;
    if (waitingOn && waitingOn !== me) {
      check = `<p class="muted small">This AI draft waits on ${esc(waitingOn)}, its owner, to check it first.</p>`;
    } else if (b.owner === me && b.ai && !hist.some(c => c.by === me)) {
      check = `<p class="small">Your AI draft. Read it, fix the wording if needed, and say it looks right.</p>
        <div class="verdicts one"><button type="button" data-v="looks_right" aria-pressed="${pend.v === "looks_right"}">Looks right</button></div>`;
    } else if (b.owner === me) {
      check = `<p class="muted small">You made this block. Others check it.</p>`;
    } else {
      check = `<div class="verdicts">${Object.entries(VERDICT).map(([v, l]) => `<button type="button" data-v="${v}" aria-pressed="${pend.v === v}">${l}</button>`).join("")}</div>
        ${pend.v === "looks_right" ? `<div class="hows">${Object.entries(HOW).map(([k, l]) => `<button type="button" data-how="${k}" aria-pressed="${pend.how === k}">${l}</button>`).join("")}</div>` : ""}
        ${pend.v && pend.v !== "looks_right" ? `<textarea id="ck-note" rows="2" placeholder="${pend.v === "disagree" ? "Why do you disagree?" : "What should change?"}"></textarea>` : ""}`;
    }
    const canSave = pend.v && !(waitingOn && waitingOn !== me);
    return `<div class="dt">
      <div class="eyebrow">${shape(b.level)}${esc(ws.label(b))}${b.ai ? " · " + aiTag(b) : ""}${q ? ` · <span class="qchip">Q${q.n}</span>` : ""}</div>
      <h2>${esc(b.text)}</h2>
      <div class="row">${stateTag(ws, b)}${troubleTags(ws, b, true)}<span class="by">by ${esc(b.owner)}</span></div>
      ${why ? `<div class="waits">Waiting on you: ${esc(why)}</div>` : ""}
      ${weak.length ? `<div class="flag"><b>⚠ Built on ${weak.length} block${weak.length > 1 ? "s" : ""} that still need a check.</b> ${weak.slice(0, 3).map(w => `<button type="button" class="linkbtn" data-go="${w.id}">${esc(ws.label(w))}</button>`).join(", ")}${weak.length > 3 ? "…" : ""}</div>` : ""}
      ${ws.restsOnNothing(b) ? `<div class="flag"><b>Rests on nothing.</b> Nothing is under this ${b.level}. Connect what it is built on, or say where it comes from.</div>` : ""}
      ${srcs.length ? `<div class="sect"><h3>From</h3>${srcs.map(x => item(ws, x)).join("")}</div>` : ""}
      ${under.length ? `<div class="sect"><h3>Built on (${under.length})</h3>${under.map(x => item(ws, x)).join("")}</div>` : ""}
      ${b.ai ? `<div class="aibox"><div><b class="${b.conf === "low" ? "warn" : ""}">AI says: ${b.conf} confidence.</b> ${esc(b.why)}</div>${b.assumes.length ? `<div>Assumes: ${b.assumes.map(esc).join("; ")}</div>` : ""}<div class="muted small">This is the AI's own view. It never counts as a check.</div></div>` : ""}
      <div class="sect yourcheck"><h3>Your check</h3>${check}
        ${canSave ? `<button type="button" class="btn primary" data-save="${b.id}">Save check</button>` : ""}</div>
      <details class="fold"><summary>Think it through</summary><ul class="asks">${(ASKS[b.level] || []).map(a => `<li>${esc(a)}</li>`).join("")}</ul></details>
      <details class="fold"${opts.openAbove ? " open" : ""}><summary>Holds up (${over.length})</summary><div class="in">${over.map(x => item(ws, x)).join("") || `<p class="muted small">Nothing is built on it yet.</p>`}</div></details>
      <details class="fold"><summary>History (${hist.length})</summary><div class="in small">${hist.map(c => `<div><b>${esc(c.by)}</b>: ${VERDICT[c.verdict]}${c.how ? ` · ${HOW[c.how]}` : ""}${c.note ? ` · ${esc(c.note)}` : ""}</div>`).join("") || `<p class="muted">No checks yet.</p>`}</div></details>
    </div>`;
  }
  function item(ws, x) {
    return `<button type="button" class="uitem" data-go="${x.id}">${x.level === "source" ? `<span class="shape source"></span>` : x.level === "decision" ? `<span class="shape decision"></span>` : shape(x.level)}<span class="s">${esc(x.text)}</span><span class="r">${x.level === "source" || x.level === "decision" ? "" : `<span class="sq s-${ws.state(x)}"></span>`}${troubleTags(ws, x)}</span></button>`;
  }

  // Wires a detail panel inside `root` to save checks. onGo(id) moves; onSaved(block) after a check.
  function wireDetail(root, ws, getId, rerender, onGo, onSaved) {
    let pending = {};
    root.addEventListener("click", e => {
      const go = e.target.closest("[data-go]");
      if (go) { pending = {}; onGo(go.dataset.go); return; }
      const v = e.target.closest("[data-v]");
      if (v) { pending = { v: v.dataset.v }; rerender(pending); return; }
      const how = e.target.closest("[data-how]");
      if (how) { pending.how = how.dataset.how; rerender(pending); return; }
      const save = e.target.closest("[data-save]");
      if (save) {
        const b = ws.get(save.dataset.save);
        const note = (root.querySelector("#ck-note") || {}).value || "";
        if (pending.v !== "looks_right" && !note.trim() && b.owner !== ws.you) { const t = root.querySelector("#ck-note"); if (t) { t.focus(); t.placeholder = "Say a few words so the owner knows what to fix."; } return; }
        ws.check(b, ws.you, pending.v, pending.how || null, note.trim());
        pending = {};
        onSaved(b);
      }
    });
    return { reset() { pending = {}; } };
  }

  function toast(msg) {
    let t = document.getElementById("toast");
    if (!t) { t = document.createElement("div"); t.id = "toast"; t.className = "toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
    t.textContent = msg; t.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, 2600);
  }

  window.ANCHOR = { build, LEVEL, STATE, VERDICT, HOW, PEOPLE, esc, shape, aiTag, troubleTags, stateTag, detail, item, wireDetail, toast };
})();
