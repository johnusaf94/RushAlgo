"""
squeeze_searcher_gui.py
========================
Standalone squeeze searcher — scans tiered universe for squeeze candidates.
Uses Keith Gill and Chamath Palihapitiya frameworks.

Requires in same folder:
  shared_utils.py, squeeze_analyzers.py, squeeze_universe.py,
  data_validator.py, ticker_resolver.py
"""

import tkinter as tk
from tkinter import scrolledtext
import threading
from shared_utils import *

PORTFOLIO_FILE = "portfolio.xlsx"


class SqueezeSearcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎯 Squeeze Searcher")
        self.root.geometry("1280x860")
        self.root.configure(bg=BG)
        self._sq_running = False
        self._sq_stop    = False
        self._sq_results = []
        self.portfolio_ctx = load_portfolio_context(PORTFOLIO_FILE)

        # Top bar
        top = tk.Frame(root, bg=BG2, pady=8)
        top.pack(fill="x")
        tk.Label(top, text="🎯 SQUEEZE SEARCHER", font=FONT_HD,
                 bg=BG2, fg=ACCENT).pack(side="left", padx=16)
        tk.Label(top, text="Scan universe for short squeeze candidates",
                 font=FONT_SM, bg=BG2, fg=FG_DIM).pack(side="left", padx=8)

        self.tab_squeeze = tk.Frame(root, bg=BG)
        self.tab_squeeze.pack(fill="both", expand=True)
        self._build_squeeze_tab()

    def _build_squeeze_tab(self):
        """Squeeze Searcher — scans S&P500 from smallest to largest market cap."""
        parent = self.tab_squeeze
        self._sq_running   = False
        self._sq_stop      = False
        self._sq_results   = []   # list of (combined_score, gill, chamath, ticker)

        # ── LEFT: Controls (fixed panel — no scroll needed) ────────────
        ctrl = tk.Frame(parent, bg=BG2, width=280)
        ctrl.pack(side="left", fill="y")
        ctrl.pack_propagate(False)

        tk.Label(ctrl, text="SQUEEZE SEARCHER", font=FONT_LG,
                 bg=BG2, fg=ACCENT).pack(pady=(14,2), padx=14, anchor="w")
        tk.Label(ctrl, text="Tiered universe — high SI names first",
                 font=FONT_SM, bg=BG2, fg=FG_DIM).pack(padx=14, anchor="w")

        tk.Frame(ctrl, bg=BORDER, height=1).pack(fill="x", padx=10, pady=8)

        # ── UNIVERSE TIER SELECTOR ──
        tk.Label(ctrl, text="SEARCH UNIVERSE", font=FONT_SM,
                 bg=BG2, fg=FG_DIM).pack(padx=14, anchor="w", pady=(0,4))

        TIER_INFO = [
            ("T1: Chronic high-SI  (~270)",  "Meme/EV/biotech — known squeeze names"),
            ("T2: + Russell 2000   (~725)",  "Small caps — primary squeeze ground"),
            ("T3: + Mid cap growth (~903)",  "Growth stocks with short crowding"),
            ("T4: Full universe  (~1,100)",  "Complete coverage"),
        ]
        self._sq_tier_var = tk.IntVar(value=2)
        self._sq_tier_lbl = tk.Label(ctrl, text=TIER_INFO[1][1],
                                      font=("Consolas",7), bg=BG2, fg=YELLOW,
                                      wraplength=240, anchor="w")
        self._sq_tier_lbl.pack(padx=14, anchor="w", pady=(0,4))

        def _update_tier(*_):
            self._sq_tier_lbl.config(text=TIER_INFO[self._sq_tier_var.get()-1][1])

        tier_f = tk.Frame(ctrl, bg=BG2)
        tier_f.pack(fill="x", padx=10, pady=(0,4))
        for i, (label, _) in enumerate(TIER_INFO, 1):
            tk.Radiobutton(tier_f, text=label, variable=self._sq_tier_var, value=i,
                           font=("Consolas",8), bg=BG2, fg=FG, selectcolor=BG3,
                           activebackground=BG2, relief="flat",
                           command=_update_tier).pack(anchor="w", pady=1)

        tk.Frame(ctrl, bg=BORDER, height=1).pack(fill="x", padx=10, pady=6)

        def labeled_sq(label, default):
            f = tk.Frame(ctrl, bg=BG2)
            f.pack(fill="x", padx=14, pady=2)
            tk.Label(f, text=label, font=FONT_SM, bg=BG2, fg=FG_DIM,
                     width=16, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(default))
            tk.Entry(f, textvariable=var, font=FONT_SM, bg=BG3, fg=FG,
                     insertbackground=FG, relief="flat", bd=4, width=8).pack(side="left")
            return var

        self._sq_max_stocks  = labeled_sq("Limit (0=all)", "0")
        self._sq_top_results = labeled_sq("Show top N", "25")

        tk.Frame(ctrl, bg=BORDER, height=1).pack(fill="x", padx=10, pady=8)

        # Squeeze thresholds
        tk.Label(ctrl, text="MINIMUM THRESHOLDS", font=FONT_SM,
                 bg=BG2, fg=FG_DIM).pack(padx=14, anchor="w", pady=(0,4))

        self._sq_min_si  = labeled_sq("Min Short Int %", "5")
        self._sq_min_dtc = labeled_sq("Min Days to Cover", "1")
        self._sq_min_score = labeled_sq("Min Combined Score", "30")

        tk.Frame(ctrl, bg=BORDER, height=1).pack(fill="x", padx=10, pady=8)

        # Agent selector
        tk.Label(ctrl, text="SQUEEZE AGENTS", font=FONT_SM,
                 bg=BG2, fg=FG_DIM).pack(padx=14, anchor="w", pady=(0,4))

        self._sq_use_gill    = tk.BooleanVar(value=True)
        self._sq_use_chamath = tk.BooleanVar(value=True)
        af = tk.Frame(ctrl, bg=BG2)
        af.pack(fill="x", padx=10)
        tk.Checkbutton(af, text="🎮 Keith Gill (DFV)",
                       variable=self._sq_use_gill,
                       font=FONT_SM, bg=BG2, fg=FG, selectcolor=BG3,
                       activebackground=BG2, relief="flat").pack(anchor="w")
        tk.Checkbutton(af, text="💰 Chamath Palihapitiya",
                       variable=self._sq_use_chamath,
                       font=FONT_SM, bg=BG2, fg=FG, selectcolor=BG3,
                       activebackground=BG2, relief="flat").pack(anchor="w")

        tk.Frame(ctrl, bg=BORDER, height=1).pack(fill="x", padx=10, pady=8)

        # Sort by
        tk.Label(ctrl, text="SORT RESULTS BY", font=FONT_SM,
                 bg=BG2, fg=FG_DIM).pack(padx=14, anchor="w", pady=(0,4))
        self._sq_sort_var = tk.StringVar(value="combined")
        sort_opts = [
            ("Combined Score",   "combined"),
            ("Gill Score",       "gill"),
            ("Chamath Score",    "chamath"),
            ("Short Interest %", "si"),
            ("Days to Cover",    "dtc"),
        ]
        for label, val in sort_opts:
            tk.Radiobutton(ctrl, text=label, variable=self._sq_sort_var, value=val,
                           font=FONT_SM, bg=BG2, fg=FG, selectcolor=BG3,
                           activebackground=BG2, relief="flat").pack(anchor="w", padx=14)

        tk.Frame(ctrl, bg=BORDER, height=1).pack(fill="x", padx=10, pady=8)

        # Run button
        self._sq_run_btn = tk.Button(ctrl, text="🎯  Start Squeeze Search",
                                      font=("Consolas",11,"bold"),
                                      bg=ACCENT, fg="#000000",
                                      relief="flat", cursor="hand2",
                                      padx=14, pady=6,
                                      command=self._sq_toggle)
        self._sq_run_btn.pack(fill="x", padx=10, pady=4)

        self._sq_status = tk.Label(ctrl, text="Ready — will scan S&P500",
                                    font=FONT_SM, bg=BG2, fg=FG_DIM, wraplength=230)
        self._sq_status.pack(padx=14, pady=4, anchor="w")

        # ── RIGHT: Results ──────────────────────────────────────────────
        right = tk.Frame(parent, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        # Progress bar at top
        prog_frame = tk.Frame(right, bg=BG2, pady=6)
        prog_frame.pack(fill="x")

        self._sq_prog_lbl = tk.Label(prog_frame, text="",
                                      font=FONT_SM, bg=BG2, fg=FG_DIM)
        self._sq_prog_lbl.pack(side="left", padx=12)

        self._sq_prog_bar_frame = tk.Frame(prog_frame, bg=BG3, height=6)
        self._sq_prog_bar_frame.pack(side="left", fill="x", expand=True, padx=8, pady=4)
        self._sq_prog_fill = tk.Frame(self._sq_prog_bar_frame, bg=ACCENT, height=6, width=0)
        self._sq_prog_fill.place(x=0, y=0, relheight=1.0)

        tk.Frame(right, bg=BORDER, height=1).pack(fill="x")

        # Results log
        self._sq_log = scrolledtext.ScrolledText(
            right, wrap="word", font=FONT_SM, bg=BG, fg=FG,
            insertbackground=FG, relief="flat", borderwidth=0,
            state="disabled", padx=16, pady=10,
        )
        self._sq_log.pack(fill="both", expand=True)

        # Tags
        for tag, cfg in [
            ("header",   {"font": FONT_LG,                    "foreground": ACCENT}),
            ("dim",      {                                      "foreground": FG_DIM}),
            ("green",    {                                      "foreground": GREEN}),
            ("red",      {                                      "foreground": RED}),
            ("yellow",   {                                      "foreground": YELLOW}),
            ("blue",     {                                      "foreground": BLUE}),
            ("strong",   {"font": ("Consolas",10,"bold"),      "foreground": GREEN}),
            ("watch",    {"font": ("Consolas",10,"bold"),      "foreground": YELLOW}),
            ("pass_tag", {"font": ("Consolas",9),              "foreground": FG_DIM}),
        ]:
            self._sq_log.tag_config(tag, **cfg)

    # ── SQUEEZE SEARCH HELPERS ───────────────────────────────────────────


    def _sq_write(self, text, tag=None):
        self._sq_log.config(state="normal")
        self._sq_log.insert("end", text, tag) if tag else self._sq_log.insert("end", text)
        self._sq_log.see("end")
        self._sq_log.config(state="disabled")
        self.root.update_idletasks()


    def _sq_toggle(self):
        if self._sq_running:
            self._sq_stop = True
            self._sq_run_btn.config(text="⏹ Stopping...", bg=RED, state="disabled")
        else:
            self._sq_start()


    def _sq_start(self):
        try:
            limit     = int(self._sq_max_stocks.get())
            top_n     = int(self._sq_top_results.get())
            min_si    = float(self._sq_min_si.get()) / 100.0
            min_dtc   = float(self._sq_min_dtc.get())
            min_score = float(self._sq_min_score.get())
        except ValueError:
            self._sq_write("❌ Invalid inputs.\n", "red")
            return

        tier        = getattr(self, "_sq_tier_var", tk.IntVar(value=2)).get()
        use_gill    = self._sq_use_gill.get()
        use_chamath = self._sq_use_chamath.get()
        sort_by     = self._sq_sort_var.get()

        if not use_gill and not use_chamath:
            self._sq_write("❌ Select at least one squeeze agent.\n", "red")
            return

        self._sq_running = True
        self._sq_stop    = False
        self._sq_results = []
        self._sq_run_btn.config(bg=RED, fg="#000000", text="⏹ Stop")

        self._sq_log.config(state="normal")
        self._sq_log.delete("1.0", "end")
        self._sq_log.config(state="disabled")

        threading.Thread(
            target=self._sq_thread,
            args=(limit, top_n, min_si, min_dtc, min_score,
                  use_gill, use_chamath, sort_by, tier),
            daemon=True,
        ).start()


    def _sq_thread(self, limit, top_n, min_si, min_dtc, min_score,
                   use_gill, use_chamath, sort_by, tier=2):
        try:
            from squeeze_analyzers import (
                run_gill_analysis, run_chamath_analysis,
                fetch_squeeze_metrics
            )

            self._sq_write("\n")
            self._sq_write("  🎯 SQUEEZE SEARCHER\n", "header")

            # ── Load universe from squeeze_universe.py ──
            self._sq_status.config(text="Loading ticker universe...")
            try:
                from squeeze_universe import get_universe
                universe = get_universe(
                    tier_max=tier,
                    limit=limit if limit > 0 else None
                )
                tier_names = {1:"Chronic+High-SI", 2:"+Russell2000",
                              3:"+MidCap", 4:"+S&P500(full)"}
                self._sq_write(
                    f"  Tier {tier} ({tier_names.get(tier,'')}) | "
                    f"{len(universe):,} tickers\n"
                    f"  Min SI: {min_si:.0%} | DTC ≥ {min_dtc:.1f}d | "
                    f"Score ≥ {min_score:.0f}\n"
                    f"  Chronic high-SI names scanned first.\n\n", "dim"
                )
            except ImportError:
                self._sq_write(
                    "  ⚠️  squeeze_universe.py not found — using fallback list\n\n",
                    "yellow"
                )
                universe = self._sq_get_broad_universe(limit or 500)

            total = len(universe)
            if total == 0:
                self._sq_write("❌ Empty universe. Check squeeze_universe.py.\n", "red")
                return

            candidates = []

            for i, ticker in enumerate(universe):
                if self._sq_stop:
                    self._sq_write("\n  ⏹ Stopped.\n", "dim")
                    break

                # Update progress bar
                pct = (i + 1) / total
                self._sq_status.config(text=f"[{i+1}/{total}] {ticker}")
                self._sq_prog_lbl.config(text=f"{i+1}/{total}")
                try:
                    bar_w = self._sq_prog_bar_frame.winfo_width()
                    self._sq_prog_fill.place(x=0, y=0,
                                              width=int(bar_w * pct),
                                              relheight=1.0)
                except Exception:
                    pass

                # Quick pre-filter: fetch raw metrics first
                try:
                    metrics = fetch_squeeze_metrics(ticker)
                except Exception as e:
                    self._sq_write(f"  ⚠️  {ticker}: fetch error — {e}\n", "dim")
                    continue

                # Pre-filter on minimum thresholds to skip obvious non-candidates fast
                si = metrics.short_interest_pct or 0
                dtc = metrics.days_to_cover or 0
                if si < min_si or dtc < min_dtc:
                    self._sq_write(
                        f"  ○ {ticker:<6}  SI:{si:.0%}  DTC:{dtc:.1f}d  — below threshold\n",
                        "pass_tag"
                    )
                    continue

                # Run full squeeze analyses
                gill_result    = None
                chamath_result = None
                gill_score     = 0
                chamath_score  = 0

                if use_gill:
                    try:
                        gill_result = run_gill_analysis(ticker)
                        gill_score  = gill_result.total_score
                    except Exception:
                        pass

                if use_chamath:
                    try:
                        chamath_result = run_chamath_analysis(ticker)
                        chamath_score  = chamath_result.total_score
                    except Exception:
                        pass

                combined = (gill_score + chamath_score) / (
                    (1 if use_gill else 0) + (1 if use_chamath else 0)
                )

                if combined < min_score:
                    self._sq_write(
                        f"  ○ {ticker:<6}  Score:{combined:.0f}  SI:{si:.0%}  DTC:{dtc:.1f}d  — score too low\n",
                        "pass_tag"
                    )
                    continue

                # Passed all filters — this is a candidate
                candidates.append({
                    "ticker":   ticker,
                    "company":  metrics.company_name,
                    "sector":   metrics.sector,
                    "gill":     gill_score,
                    "chamath":  chamath_score,
                    "combined": combined,
                    "si":       si,
                    "dtc":      dtc,
                    "ctb":      metrics.ctb_proxy,
                    "price":    metrics.current_price,
                    "mktcap":   metrics.market_cap,
                    "gill_obj": gill_result,
                    "ch_obj":   chamath_result,
                    "verdict":  gill_result.verdict if gill_result else (chamath_result.verdict if chamath_result else ""),
                })

                verdict_tag = "strong" if combined >= 60 else "watch"
                self._sq_write(
                    f"  ✅ {ticker:<6}  Combined:{combined:.0f}  "
                    f"Gill:{gill_score:.0f}  Chamath:{chamath_score:.0f}  "
                    f"SI:{si:.0%}  DTC:{dtc:.1f}d\n",
                    verdict_tag
                )

            # ── Sort and display final results ──
            sort_key = {
                "combined": lambda x: x["combined"],
                "gill":     lambda x: x["gill"],
                "chamath":  lambda x: x["chamath"],
                "si":       lambda x: x["si"],
                "dtc":      lambda x: x["dtc"],
            }.get(sort_by, lambda x: x["combined"])

            candidates.sort(key=sort_key, reverse=True)
            self._sq_results = candidates

            self._sq_write("\n")
            self._sq_write(f"  {'─'*70}\n", "dim")
            self._sq_write(f"  TOP SQUEEZE CANDIDATES\n", "header")
            self._sq_write(f"  Sorted by: {sort_by}  |  "
                           f"Found {len(candidates)} candidates from {i+1} scanned\n\n", "dim")

            if not candidates:
                self._sq_write("  No candidates found matching your criteria.\n", "yellow")
                self._sq_write("  Try lowering Min Short Interest % or Min Score.\n", "dim")
            else:
                # Header
                self._sq_write(
                    f"  {'Rank':<5} {'Ticker':<7} {'Company':<22} {'Sector':<20} "
                    f"{'Comb':>5}  {'Gill':>5}  {'Cham':>5}  "
                    f"{'SI':>6}  {'DTC':>5}  {'CTB':>6}  {'MktCap':>8}\n", "blue"
                )
                self._sq_write(f"  {'─'*105}\n", "dim")

                for rank, c in enumerate(candidates[:top_n], 1):
                    mc_str  = f"${c['mktcap']/1e9:.1f}B" if c.get("mktcap") else "N/A"
                    ctb_str = f"{c['ctb']:.0f}%" if c.get("ctb") else "N/A"
                    tag = "strong" if c["combined"] >= 60 else "watch"

                    self._sq_write(
                        f"  #{rank:<4} {c['ticker']:<7} {c['company'][:22]:<22} "
                        f"{c['sector'][:20]:<20} "
                        f"{c['combined']:>5.0f}  {c['gill']:>5.0f}  {c['chamath']:>5.0f}  "
                        f"{c['si']:>6.1%}  {c['dtc']:>5.1f}  {ctb_str:>6}  {mc_str:>8}\n",
                        tag
                    )

                # Detailed breakdown for top 3
                self._sq_write(f"\n  {'─'*70}\n", "dim")
                self._sq_write(f"  DETAILED BREAKDOWN — TOP 3\n\n", "header")

                from squeeze_analyzers import format_gill_display, format_chamath_display
                for c in candidates[:3]:
                    self._sq_write(f"  {'='*68}\n", "dim")
                    self._sq_write(f"  #{candidates.index(c)+1}  {c['ticker']} — {c['company']}\n", "strong")
                    self._sq_write(f"  Combined Score: {c['combined']:.0f}  |  "
                                   f"Verdict: {c['verdict']}\n\n", "watch")
                    if c.get("gill_obj") and use_gill:
                        self._sq_write(f"  🎮 KEITH GILL\n", "blue")
                        self._sq_write(format_gill_display(c["gill_obj"]), "dim")
                    if c.get("ch_obj") and use_chamath:
                        self._sq_write(f"  💰 CHAMATH\n", "blue")
                        self._sq_write(format_chamath_display(c["ch_obj"]), "dim")

            self._sq_prog_lbl.config(text=f"Done — {len(candidates)} candidates")
            self._sq_status.config(text=f"Done — {len(candidates)} squeeze candidates found")

        except Exception as e:
            import traceback
            self._sq_write(f"\n❌ Error: {e}\n", "red")
            self._sq_write(traceback.format_exc(), "dim")
            self._sq_status.config(text="Error")
        finally:
            self._sq_running = False
            self._sq_stop    = False
            self._sq_run_btn.config(state="normal", text="🎯  Start Squeeze Search",
                                     bg=ACCENT, fg="#000000")


    def _sq_get_sp500_by_marketcap(self, ascending=True) -> list:
        """
        Fetch S&P500 tickers sorted by market cap.
        ascending=True → smallest first (more squeeze candidates at small cap).
        Returns list of ticker strings.
        """
        import yfinance as yf

        tickers = []

        # Method 1: Wikipedia via requests + html.parser (no lxml needed)
        try:
            import pandas as pd
            import requests
            resp = requests.get(
                "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                headers={"User-Agent": "Mozilla/5.0"}, timeout=15
            )
            sp500 = pd.read_html(resp.text, attrs={"id": "constituents"})[0]
            sym_col = "Symbol" if "Symbol" in sp500.columns else sp500.columns[0]
            tickers = sp500[sym_col].str.replace(".", "-", regex=False).tolist()
            self._sq_write(f"  📋 Wikipedia: {len(tickers)} S&P500 tickers\n", "dim")
        except Exception as e:
            self._sq_write(f"  ⚠️  Wikipedia method failed: {e}\n", "dim")

        # Method 2: yfinance screener for US large/mid cap equities
        if not tickers:
            try:
                import yfinance as yf
                screener = yf.Screener()
                screener.set_body({
                    "offset": 0, "size": 500,
                    "sortField": "intradaymarketcap", "sortType": "DESC",
                    "quoteType": "EQUITY",
                    "query": {
                        "operator": "and",
                        "operands": [
                            {"operator": "eq",  "operands": ["region", "us"]},
                            {"operator": "gt",  "operands": ["intradaymarketcap", 2_000_000_000]},
                        ]
                    },
                    "userId": "", "userIdType": "guest"
                })
                quotes = screener.response.get("quotes", [])
                tickers = [q["symbol"] for q in quotes if q.get("symbol")]
                self._sq_write(f"  📋 Screener: {len(tickers)} large/mid cap tickers\n", "dim")
            except Exception as e:
                self._sq_write(f"  ⚠️  Screener method failed: {e}\n", "dim")

        # Method 3: Hardcoded S&P500-representative list as last resort
        if not tickers:
            self._sq_write("  ⚠️  Using built-in representative ticker list\n", "yellow")
            tickers = [
                # Small/micro cap (most squeeze candidates)
                "BBAI","MARA","RIOT","CLSK","CIFR","HUT","BTBT","ARBK",
                "SRRK","NKLA","RIDE","WKHS","GOEV","MULN","FFIE","CENN",
                "SPCE","JOBY","LILM","ACHR","EVTL","EHGO","GREE","HIVE",
                # Mid cap
                "GME","AMC","BBBY","KOSS","EXPR","NAKD","SNDL","CLOV",
                "WISH","WOOF","PAYO","OPEN","OFSG","PRCH","SKLZ","DKNG",
                # Large cap (lower squeeze probability but included)
                "NVDA","AMD","TSLA","META","GOOGL","MSFT","AAPL","AMZN",
                "JPM","BAC","WFC","GS","MS","C","USB","PNC","TFC","FITB",
                "XOM","CVX","COP","SLB","HAL","DVN","EOG","PXD","MPC","VLO",
                "LLY","UNH","JNJ","ABBV","MRK","ABT","TMO","DHR","ISRG","REGN",
            ]

        if not tickers:
            self._sq_write("  ❌ Could not build ticker list from any source.\n", "red")
            return []

        self._sq_write(f"  📋 Got {len(tickers)} S&P500 tickers — fetching market caps...\n", "dim")

        # Fetch market caps in bulk using yfinance download
        # Use info for a batch — this is slow but necessary for sorting
        # Speed optimization: use fast_info which is cached
        ticker_caps = {}
        batch_size = 50

        for i in range(0, min(len(tickers), 500), batch_size):
            batch = tickers[i:i+batch_size]
            if self._sq_stop:
                break
            try:
                # Download to get tickers validated, then pull fast_info
                for t in batch:
                    try:
                        fast = yf.Ticker(t).fast_info
                        mc = getattr(fast, "market_cap", None)
                        ticker_caps[t] = mc if mc else 0
                    except Exception:
                        ticker_caps[t] = 0
            except Exception:
                for t in batch:
                    ticker_caps[t] = 0

            self._sq_status.config(text=f"Sorting by market cap... {i+batch_size}/{len(tickers)}")

        # Sort by market cap
        sorted_tickers = sorted(
            ticker_caps.keys(),
            key=lambda t: ticker_caps.get(t, 0),
            reverse=not ascending
        )

        cap_order = "smallest → largest" if ascending else "largest → smallest"
        self._sq_write(f"  ✅ Sorted {len(sorted_tickers)} tickers by market cap ({cap_order})\n\n", "dim")
        return sorted_tickers


if __name__ == "__main__":
    root = tk.Tk()
    app = SqueezeSearcherApp(root)
    root.mainloop()
