"""
squeeze_analyzer_gui.py
========================
Standalone single-stock squeeze analyzer.
Runs Keith Gill (DFV) and Chamath Palihapitiya squeeze frameworks.

Requires in same folder:
  shared_utils.py, squeeze_analyzers.py, data_validator.py, ticker_resolver.py
"""

import tkinter as tk
from tkinter import scrolledtext
import threading
from shared_utils import *

PORTFOLIO_FILE = "portfolio.xlsx"


class SqueezeAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🔬 Squeeze Analyzer")
        self.root.geometry("1280x820")
        self.root.configure(bg=BG)
        self._sa_running = False
        self._sa_stop    = False
        self._sa_results = None
        self.portfolio_ctx = load_portfolio_context(PORTFOLIO_FILE)

        top = tk.Frame(root, bg=BG2, pady=8)
        top.pack(fill="x")
        tk.Label(top, text="🔬 SQUEEZE ANALYZER", font=FONT_HD,
                 bg=BG2, fg=ACCENT).pack(side="left", padx=16)
        tk.Label(top, text="Single-stock: Keith Gill + Chamath Palihapitiya",
                 font=FONT_SM, bg=BG2, fg=FG_DIM).pack(side="left", padx=8)

        self.tab_squeeze_single = tk.Frame(root, bg=BG)
        self.tab_squeeze_single.pack(fill="both", expand=True)
        self._build_squeeze_analyzer_tab()

    def _build_squeeze_analyzer_tab(self):
        parent = self.tab_squeeze_single
        self._sa_running = False
        self._sa_stop    = False
        self._sa_results = None
        main = tk.Frame(parent, bg=BG)
        main.pack(fill="both", expand=True)
        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        self._sa_chat = scrolledtext.ScrolledText(
            left, wrap="word", font=FONT, bg=BG, fg=FG,
            insertbackground=FG, selectbackground=BORDER,
            relief="flat", borderwidth=0, state="disabled", padx=20, pady=16)
        self._sa_chat.pack(fill="both", expand=True)
        for tag, cfg in [
            ("header",       {"font": FONT_LG, "foreground": ACCENT}),
            ("dim",          {"foreground": FG_DIM}),
            ("green",        {"foreground": GREEN}),
            ("red",          {"foreground": RED}),
            ("yellow",       {"foreground": YELLOW}),
            ("blue",         {"foreground": BLUE}),
            ("score_strong", {"font": ("Consolas",12,"bold"), "foreground": GREEN}),
            ("score_watch",  {"font": ("Consolas",11,"bold"), "foreground": YELLOW}),
            ("score_pass",   {"font": ("Consolas",11,"bold"), "foreground": RED}),
            ("claude",       {"font": ("Consolas",10), "foreground": TEAL}),
        ]:
            self._sa_chat.tag_config(tag, **cfg)
        sb = tk.Frame(main, bg=BG2, width=250)
        sb.pack(side="right", fill="y")
        sb.pack_propagate(False)
        tk.Label(sb, text="SQUEEZE SCORE", font=FONT_SM, bg=BG2, fg=FG_DIM).pack(pady=(14,2), padx=10, anchor="w")
        box = tk.Frame(sb, bg=BG3)
        box.pack(fill="x", padx=6, pady=2)
        self._sa_lbl_ticker  = tk.Label(box, text="—", font=FONT_LG, bg=BG3, fg=ACCENT)
        self._sa_lbl_ticker.pack(pady=(8,0))
        self._sa_lbl_gill    = tk.Label(box, text="Gill: —", font=("Consolas",10,"bold"), bg=BG3, fg=FG_DIM)
        self._sa_lbl_gill.pack()
        self._sa_lbl_chamath = tk.Label(box, text="Chamath: —", font=("Consolas",10,"bold"), bg=BG3, fg=FG_DIM)
        self._sa_lbl_chamath.pack()
        self._sa_lbl_combined = tk.Label(box, text="—", font=("Consolas",28,"bold"), bg=BG3, fg=FG_DIM)
        self._sa_lbl_combined.pack(pady=(4,0))
        self._sa_lbl_verdict = tk.Label(box, text="—", font=("Consolas",9,"bold"), bg=BG3, fg=FG_DIM, wraplength=220)
        self._sa_lbl_verdict.pack(pady=(0,8), padx=6)
        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", padx=6, pady=6)
        tk.Label(sb, text="KEY METRICS", font=FONT_SM, bg=BG2, fg=FG_DIM).pack(anchor="w", padx=10, pady=(0,4))
        self._sa_metrics_frame = tk.Frame(sb, bg=BG2)
        self._sa_metrics_frame.pack(fill="x", padx=6)
        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", padx=6, pady=6)
        tk.Label(sb, text="AGENTS", font=FONT_SM, bg=BG2, fg=FG_DIM).pack(anchor="w", padx=10, pady=(0,4))
        self._sa_use_gill    = tk.BooleanVar(value=True)
        self._sa_use_chamath = tk.BooleanVar(value=True)
        af2 = tk.Frame(sb, bg=BG2)
        af2.pack(fill="x", padx=8)
        for text, var in [("🎮 Keith Gill (DFV)", self._sa_use_gill),
                           ("💰 Chamath Palihapitiya", self._sa_use_chamath)]:
            tk.Checkbutton(af2, text=text, variable=var, font=FONT_SM,
                           bg=BG2, fg=FG, selectcolor=BG3,
                           activebackground=BG2, relief="flat").pack(anchor="w")
        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", padx=6, pady=6)
        tk.Button(sb, text="Clear", font=FONT_SM, bg=BG3, fg=FG_DIM,
                  relief="flat", cursor="hand2", command=self._sa_clear).pack(fill="x", padx=6, pady=2)
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x")
        bot = tk.Frame(parent, bg=BG2, pady=8)
        bot.pack(fill="x")
        r1 = tk.Frame(bot, bg=BG2)
        r1.pack(fill="x", padx=12, pady=(0,4))
        tk.Label(r1, text="Ticker:", font=FONT, bg=BG2, fg=FG_DIM).pack(side="left")
        self._sa_ticker_var = tk.StringVar()
        self._sa_ticker_entry = tk.Entry(r1, textvariable=self._sa_ticker_var, font=FONT,
                                          bg=BG3, fg=FG, insertbackground=FG, relief="flat", bd=6, width=12)
        self._sa_ticker_entry.pack(side="left", padx=6)
        self._sa_ticker_entry.bind("<Return>", lambda e: self._sa_toggle())
        self._sa_run_btn = tk.Button(r1, text="▶  Analyze", font=("Consolas",11,"bold"),
                                      bg=ACCENT, fg="#000000", relief="flat",
                                      cursor="hand2", padx=14, pady=4, command=self._sa_toggle)
        self._sa_run_btn.pack(side="left", padx=4)
        self._sa_status_lbl = tk.Label(r1, text="Ready", font=FONT_SM, bg=BG2, fg=FG_DIM)
        self._sa_status_lbl.pack(side="left", padx=10)
        tk.Frame(bot, bg=BORDER, height=1).pack(fill="x")
        r2 = tk.Frame(bot, bg=BG, pady=6)
        r2.pack(fill="x", padx=12)
        tk.Label(r2, text="Ask Claude:", font=FONT, bg=BG, fg=FG_DIM).pack(side="left")
        self._sa_qa_var = tk.StringVar()
        self._sa_qa_entry = tk.Entry(r2, textvariable=self._sa_qa_var, font=FONT,
                                      bg=BG3, fg=FG_DIM, insertbackground=FG, relief="flat", bd=6, state="disabled")
        self._sa_qa_entry.pack(side="left", fill="x", expand=True, padx=6)
        self._sa_qa_entry.bind("<Return>", lambda e: self._sa_ask_claude())
        self._sa_qa_btn = tk.Button(r2, text="💬 Ask", font=("Consolas",10,"bold"),
                                     bg=BG3, fg=FG_DIM, relief="flat", cursor="hand2",
                                     padx=10, pady=4, state="disabled", command=self._sa_ask_claude)
        self._sa_qa_btn.pack(side="left", padx=4)


    def _sa_w(self, text, tag=None):
        def _do():
            self._sa_chat.config(state="normal")
            if tag: self._sa_chat.insert("end", text, tag)
            else:   self._sa_chat.insert("end", text)
            self._sa_chat.see("end")
            self._sa_chat.config(state="disabled")
        self.root.after(0, _do)


    def _sa_rule(self, label=""):
        pad = max(0, (60 - len(label) - 2) // 2) if label else 0
        self._sa_w(f"\n{'─'*pad} {label} {'─'*pad}\n\n" if label else f"\n{'─'*60}\n\n", "dim")


    def _sa_clear(self):
        self._sa_chat.config(state="normal")
        self._sa_chat.delete("1.0", "end")
        self._sa_chat.config(state="disabled")
        self._sa_results = None
        self._sa_lbl_ticker.config(text="—", fg=ACCENT)
        self._sa_lbl_gill.config(text="Gill: —", fg=FG_DIM)
        self._sa_lbl_chamath.config(text="Chamath: —", fg=FG_DIM)
        self._sa_lbl_combined.config(text="—", fg=FG_DIM)
        self._sa_lbl_verdict.config(text="—", fg=FG_DIM)
        for w in self._sa_metrics_frame.winfo_children(): w.destroy()
        self._sa_qa_entry.config(state="disabled", fg=FG_DIM)
        self._sa_qa_btn.config(state="disabled", bg=BG3, fg=FG_DIM)


    def _sa_toggle(self):
        if self._sa_running:
            self._sa_stop = True
            self._sa_run_btn.config(text="⏹ Stopping...", bg=RED, state="disabled")
        else:
            ticker = self._sa_ticker_var.get().strip().upper()
            if not ticker: self._sa_ticker_entry.focus(); return
            self._sa_start(ticker)


    def _sa_start(self, ticker):
        self._sa_running = True
        self._sa_stop    = False
        self._sa_results = None
        self._sa_run_btn.config(bg=RED, fg="#000000", text="⏹ Stop")
        self._sa_ticker_entry.config(state="disabled")
        self._sa_qa_entry.config(state="disabled", fg=FG_DIM)
        self._sa_qa_btn.config(state="disabled", bg=BG3, fg=FG_DIM)
        self._sa_status_lbl.config(text=f"Analyzing {ticker}...")
        self._sa_chat.config(state="normal")
        self._sa_chat.delete("1.0", "end")
        self._sa_chat.config(state="disabled")
        threading.Thread(target=self._sa_thread, args=(ticker,), daemon=True).start()


    def _sa_thread(self, ticker):
        try:
            from squeeze_analyzers import (run_gill_analysis, run_chamath_analysis,
                                            format_gill_display, format_chamath_display,
                                            fetch_squeeze_metrics)
            use_gill    = self._sa_use_gill.get()
            use_chamath = self._sa_use_chamath.get()
            self._sa_w(f"\n🔬  SQUEEZE ANALYSIS — {ticker}\n", "header")
            self._sa_rule()
            self.root.after(0, lambda: self._sa_status_lbl.config(text="Fetching data..."))
            metrics = fetch_squeeze_metrics(ticker)
            if metrics.fetch_errors:
                self._sa_w(f"  ⚠️  {'; '.join(metrics.fetch_errors[:2])}\n", "yellow")
            self._sa_rule("📊 Short Interest Data")
            self._sa_w(f"  Company:  {metrics.company_name}\n", "blue")
            self._sa_w(f"  Sector:   {metrics.sector}\n", "dim")
            if metrics.current_price: self._sa_w(f"  Price:    ${metrics.current_price:.2f}\n", "dim")
            if metrics.market_cap:    self._sa_w(f"  Mkt Cap:  ${metrics.market_cap/1e9:.2f}B\n", "dim")
            self._sa_w("\n")
            si_note = f" [{metrics.si_data_quality}]" if metrics.si_data_quality else ""
            self._sa_w(f"  {'Metric':<28} {'Value':<16} Threshold\n", "header")
            self._sa_w(f"  {'─'*60}\n", "dim")
            def mrow(lbl, val, ctx, thresh=None, raw=None):
                tag = "green" if (thresh and raw and raw >= thresh) else ("yellow" if thresh else "dim")
                self._sa_w(f"  {lbl:<28} {val:<16} {ctx}\n", tag)
            mrow("Short Interest % Float", f"{metrics.short_interest_pct:.1%}{si_note}" if metrics.short_interest_pct else "N/A", "> 20% (Gill)", 0.20, metrics.short_interest_pct)
            mrow("Days to Cover (DTC)", f"{metrics.days_to_cover:.1f}d" if metrics.days_to_cover else "N/A", "> 5 days", 5.0, metrics.days_to_cover)
            mrow("CTB Proxy", f"{metrics.ctb_proxy:.1f}%" if metrics.ctb_proxy else "N/A", "> 10%", 10.0, metrics.ctb_proxy)
            mrow("Shares Short", f"{metrics.shares_short:,}" if metrics.shares_short else "N/A", "")
            mrow("Float Shares", f"{metrics.float_shares:,}" if metrics.float_shares else "N/A", "")
            mrow("Short Change", f"{metrics.short_change_pct:+.1%}" if metrics.short_change_pct is not None else "N/A", "+ = adding")
            mrow("FTD % Float", f"{metrics.ftd_pct_float:.3%}" if metrics.ftd_pct_float else "N/A", "SEC data")
            mrow("Volume Surge", f"{metrics.volume_surge:.2f}x" if metrics.volume_surge else "N/A", "vs 20d avg")
            mrow("RSI (14)", f"{metrics.rsi_14:.0f}" if metrics.rsi_14 else "N/A", "< 70 preferred")
            mrow("1-Month Return", f"{metrics.price_change_1m:+.1%}" if metrics.price_change_1m is not None else "N/A", "")
            mrow("3-Month Return", f"{metrics.price_change_3m:+.1%}" if metrics.price_change_3m is not None else "N/A", "")
            self._sa_w("\n")
            if self._sa_stop: self._sa_w("  ⏹ Stopped.\n", "dim"); return
            gill_score = chamath_score = 0.0
            gill_result = chamath_result = None
            if use_gill:
                self.root.after(0, lambda: self._sa_status_lbl.config(text="Running Gill..."))
                self._sa_rule("🎮 Keith Gill — DeepFuckingValue")
                gill_result = run_gill_analysis(ticker)
                gill_score  = gill_result.total_score
                self._sa_w(format_gill_display(gill_result), "dim")
            if not self._sa_stop and use_chamath:
                self.root.after(0, lambda: self._sa_status_lbl.config(text="Running Chamath..."))
                self._sa_rule("💰 Chamath Palihapitiya")
                chamath_result = run_chamath_analysis(ticker)
                chamath_score  = chamath_result.total_score
                self._sa_w(format_chamath_display(chamath_result), "dim")
            active   = sum([use_gill, use_chamath])
            combined = (gill_score + chamath_score) / max(active, 1)
            self._sa_rule("📋 Combined Verdict")
            self._sa_w(f"  {'Agent':<22} {'Score':>8}  Verdict\n", "blue")
            self._sa_w(f"  {'─'*55}\n", "dim")
            if use_gill and gill_result:
                t = "green" if gill_score >= 55 else ("yellow" if gill_score >= 38 else "dim")
                self._sa_w(f"  {'Keith Gill':<22} {gill_score:>7.0f}  {gill_result.verdict} ({gill_result.conviction})\n", t)
            if use_chamath and chamath_result:
                t = "green" if chamath_score >= 70 else ("yellow" if chamath_score >= 50 else "dim")
                self._sa_w(f"  {'Chamath':<22} {chamath_score:>7.0f}  {chamath_result.verdict}\n", t)
            self._sa_w(f"  {'─'*55}\n", "dim")
            comb_tag = "score_strong" if combined >= 65 else ("score_watch" if combined >= 45 else "score_pass")
            self._sa_w(f"  {'COMBINED':<22} {combined:>7.0f}\n", comb_tag)
            overall = ("SQUEEZE CANDIDATE 🔥" if combined >= 65 else
                       ("WATCH — Setup Building ⚠️" if combined >= 45 else "PASS — No Squeeze Setup"))
            self._sa_w(f"\n  {overall}\n\n", comb_tag)
            self._sa_rule()
            self._sa_results = {"ticker": ticker, "metrics": metrics,
                                 "gill": gill_result, "chamath": chamath_result,
                                 "combined": combined, "overall": overall}
            def _update_sb():
                cc = GREEN if combined >= 65 else (YELLOW if combined >= 45 else RED)
                self._sa_lbl_ticker.config(text=ticker)
                self._sa_lbl_combined.config(text=f"{combined:.0f}", fg=cc)
                self._sa_lbl_verdict.config(text=overall, fg=cc)
                if use_gill:
                    gc = GREEN if gill_score >= 55 else (YELLOW if gill_score >= 38 else RED)
                    self._sa_lbl_gill.config(text=f"Gill:    {gill_score:.0f}/100", fg=gc)
                if use_chamath:
                    cc2 = GREEN if chamath_score >= 70 else (YELLOW if chamath_score >= 50 else RED)
                    self._sa_lbl_chamath.config(text=f"Chamath: {chamath_score:.0f}/100", fg=cc2)
                for w in self._sa_metrics_frame.winfo_children(): w.destroy()
                for lbl, val, col in [
                    ("SI% Float", f"{metrics.short_interest_pct:.1%}" if metrics.short_interest_pct else "N/A", GREEN if (metrics.short_interest_pct or 0) >= 0.20 else YELLOW),
                    ("DTC",       f"{metrics.days_to_cover:.1f}d" if metrics.days_to_cover else "N/A", GREEN if (metrics.days_to_cover or 0) >= 5 else YELLOW),
                    ("CTB",       f"{metrics.ctb_proxy:.0f}%" if metrics.ctb_proxy else "N/A", GREEN if (metrics.ctb_proxy or 0) >= 10 else YELLOW),
                    ("FTD",       f"{metrics.ftd_pct_float:.3%}" if metrics.ftd_pct_float else "None", FG_DIM),
                    ("RSI",       f"{metrics.rsi_14:.0f}" if metrics.rsi_14 else "N/A", FG_DIM),
                    ("Vol Surge", f"{metrics.volume_surge:.1f}x" if metrics.volume_surge else "N/A", GREEN if (metrics.volume_surge or 0) >= 2.0 else FG_DIM),
                ]:
                    rw = tk.Frame(self._sa_metrics_frame, bg=BG2)
                    rw.pack(fill="x", pady=1)
                    tk.Label(rw, text=lbl, font=FONT_SM, bg=BG2, fg=FG_DIM, width=10, anchor="w").pack(side="left")
                    tk.Label(rw, text=val, font=FONT_SM, bg=BG2, fg=col, anchor="e").pack(side="right")
                self._sa_qa_entry.config(state="normal", fg=FG)
                self._sa_qa_btn.config(state="normal", bg="#238636", fg="#FFFFFF")
            self.root.after(0, _update_sb)
            self._sa_w("  💬 Ask Claude about this analysis below\n", "dim")
            self.root.after(0, lambda: self._sa_status_lbl.config(text=f"Done — {combined:.0f}  {overall}"))
        except Exception as e:
            import traceback
            self._sa_w(f"\n❌ Error: {e}\n", "red")
            self._sa_w(traceback.format_exc() + "\n", "dim")
            self.root.after(0, lambda: self._sa_status_lbl.config(text="Error"))
        finally:
            self._sa_running = False
            self._sa_stop    = False
            self.root.after(0, lambda: [
                self._sa_run_btn.config(state="normal", text="▶  Analyze", bg=ACCENT, fg="#000000"),
                self._sa_ticker_entry.config(state="normal"),
                self._sa_ticker_var.set(""),
                self._sa_ticker_entry.focus(),
            ])


    def _sa_ask_claude(self):
        if self._sa_running or not self._sa_results: return
        question = self._sa_qa_var.get().strip()
        if not question: self._sa_qa_entry.focus(); return
        self._sa_running = True
        self._sa_qa_btn.config(state="disabled", text="⏳")
        self._sa_qa_entry.config(state="disabled")
        self._sa_run_btn.config(state="disabled")
        threading.Thread(target=self._sa_claude_thread, args=(question,), daemon=True).start()


    def _sa_claude_thread(self, question):
        try:
            r = self._sa_results
            m = r["metrics"]
            lines = [f"SQUEEZE ANALYSIS — {r['ticker']}", f"Combined: {r['combined']:.0f}/100 — {r['overall']}",
                     f"SI: {m.short_interest_pct:.1%}" if m.short_interest_pct else "SI: N/A",
                     f"DTC: {m.days_to_cover:.1f}d" if m.days_to_cover else "DTC: N/A"]
            if r.get("gill"):
                lines += [f"GILL: {r['gill'].total_score:.0f}/100 — {r['gill'].verdict}",
                          "Green: " + "; ".join(r['gill'].green_flags[:3])]
            if r.get("chamath"):
                lines.append(f"CHAMATH: {r['chamath'].total_score:.0f}/100 — {r['chamath'].verdict}")
            context = "\n".join(l for l in lines if l)
            self._sa_rule("Claude Q&A")
            self._sa_w(f"  Q: {question}\n\n", "blue")
            self._sa_w("  ⏳ Thinking...\n", "dim")
            answer = ask_lm_studio(question, context, self.portfolio_ctx)
            self._sa_chat.config(state="normal")
            pos = self._sa_chat.search("  ⏳ Thinking...", "1.0", "end")
            if pos: self._sa_chat.delete(pos, f"{pos} lineend+1c")
            self._sa_chat.config(state="disabled")
            self._sa_w(f"  {answer}\n\n", "claude")
        except Exception as e:
            self._sa_w(f"  ❌ Error: {e}\n", "red")
        finally:
            self._sa_running = False
            self.root.after(0, lambda: [
                self._sa_qa_btn.config(state="normal", text="💬 Ask", bg="#238636", fg="#FFFFFF"),
                self._sa_qa_entry.config(state="normal", fg=FG),
                self._sa_run_btn.config(state="normal"),
                self._sa_qa_var.set(""),
                self._sa_qa_entry.focus(),
            ])


if __name__ == "__main__":
    root = tk.Tk()
    app = SqueezeAnalyzerApp(root)
    root.mainloop()
