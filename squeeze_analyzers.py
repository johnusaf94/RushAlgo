"""
squeeze_analyzers.py  (v2 — data_validator powered)
=====================================================
All data now flows through data_validator.fetch_validated_info()
which fixes:
  - Dividend yield 100x bug
  - Short interest % calculated from float (not shares outstanding)
  - Growth rate scaling inconsistencies
  - DTC cross-validated against raw components
  - CTB proxy enhanced with SEC FTD data
  - NaN/None/empty unified
"""

import yfinance as yf
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


# ─────────────────────────────────────────────
# THRESHOLDS
# ─────────────────────────────────────────────
GILL_SHORT_INTEREST_MIN  = 0.20
GILL_DTC_MIN             = 5.0
GILL_CTB_PROXY_MIN       = 10.0
GILL_PE_MAX              = 30.0
GILL_REVENUE_GROWTH_MIN  = 0.0

CHAMATH_SHORT_INTEREST_MIN = 0.15
CHAMATH_MOMENTUM_MIN       = 0.05
CHAMATH_INSIDER_THRESHOLD  = 0.05


# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class SqueezeMetrics:
    ticker:                  str = ""
    company_name:            str = ""
    sector:                  str = ""

    short_interest_pct:      Optional[float] = None
    shares_short:            Optional[int]   = None
    float_shares:            Optional[int]   = None
    avg_daily_volume:        Optional[float] = None
    days_to_cover:           Optional[float] = None
    ctb_proxy:               Optional[float] = None
    si_data_quality:         str = ""

    # FTD data
    ftd_shares:              Optional[int]   = None
    ftd_pct_float:           Optional[float] = None
    ftd_report_date:         str = ""

    current_price:           Optional[float] = None
    price_change_1m:         Optional[float] = None
    price_change_3m:         Optional[float] = None
    rsi_14:                  Optional[float] = None
    volume_surge:            Optional[float] = None

    pe_ratio:                Optional[float] = None
    revenue_growth:          Optional[float] = None
    free_cash_flow:          Optional[float] = None
    debt_to_equity:          Optional[float] = None
    market_cap:              Optional[float] = None

    insider_ownership:       Optional[float] = None
    institutional_ownership: Optional[float] = None
    short_change_pct:        Optional[float] = None

    fetch_errors:            list = field(default_factory=list)


@dataclass
class GillAnalysis:
    ticker:               str = ""
    metrics:              SqueezeMetrics = field(default_factory=SqueezeMetrics)
    squeeze_setup_score:  float = 0.0
    fundamental_score:    float = 0.0
    catalyst_score:       float = 0.0
    total_score:          float = 0.0
    verdict:              str = ""
    conviction:           str = ""
    thesis:               str = ""
    red_flags:            list = field(default_factory=list)
    green_flags:          list = field(default_factory=list)


@dataclass
class ChamathAnalysis:
    ticker:                  str = ""
    metrics:                 SqueezeMetrics = field(default_factory=SqueezeMetrics)
    macro_setup_score:       float = 0.0
    squeeze_pressure_score:  float = 0.0
    catalyst_momentum_score: float = 0.0
    total_score:             float = 0.0
    verdict:                 str = ""
    narrative:               str = ""
    thesis:                  str = ""
    red_flags:               list = field(default_factory=list)
    green_flags:             list = field(default_factory=list)


# ─────────────────────────────────────────────
# SHARED DATA FETCHER — uses data_validator
# ─────────────────────────────────────────────

def fetch_squeeze_metrics(ticker: str) -> SqueezeMetrics:
    """
    Fetch all squeeze-relevant data using data_validator for accuracy.
    All fields are validated and normalised before use.
    """
    from data_validator import fetch_validated_info

    m = SqueezeMetrics(ticker=ticker.upper())

    try:
        v = fetch_validated_info(ticker)

        if v.get('_fetch_error'):
            m.fetch_errors.append(v['_fetch_error'])
            return m

        m.company_name           = v.get('longName', ticker)
        m.sector                 = v.get('sector', 'Unknown') or 'Unknown'
        m.current_price          = v.get('currentPrice')
        m.market_cap             = v.get('marketCap')
        m.pe_ratio               = v.get('trailingPE')
        m.revenue_growth         = v.get('revenueGrowth')   # already normalised
        m.free_cash_flow         = v.get('freeCashflow')
        m.debt_to_equity         = v.get('debtToEquity')
        m.insider_ownership      = v.get('heldPercentInsiders')
        m.institutional_ownership= v.get('heldPercentInstitutions')

        # Short interest — recalculated correctly by data_validator
        m.short_interest_pct     = v.get('shortPercentOfFloat')
        m.shares_short           = v.get('sharesShort')
        m.float_shares           = v.get('floatShares')
        m.days_to_cover          = v.get('shortRatio')
        m.short_change_pct       = v.get('shortChangePercent')
        m.si_data_quality        = v.get('si_data_quality', '')
        m.avg_daily_volume       = v.get('averageVolume10days') or v.get('averageVolume')

        # FTD data from SEC
        m.ftd_shares             = v.get('ftdShares')
        m.ftd_pct_float          = v.get('ftdPctFloat')
        m.ftd_report_date        = v.get('ftdReportDate', '')

        # CTB proxy (enhanced with FTD)
        m.ctb_proxy              = v.get('ctbProxy')

        # Price action from history
        hist = v.get('_history')
        if hist is not None and not hist.empty:
            prices  = hist["Close"]
            volumes = hist["Volume"]
            n = len(prices)

            if n >= 21:
                m.price_change_1m = float((prices.iloc[-1] / prices.iloc[-21]) - 1)
            if n >= 65:
                m.price_change_3m = float((prices.iloc[-1] / prices.iloc[-65]) - 1)

            # RSI-14
            delta = prices.diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean()
            rs    = gain / loss
            rsi   = 100 - (100 / (1 + rs))
            if not rsi.empty:
                m.rsi_14 = float(rsi.iloc[-1])

            # Volume surge: recent 5d vs 20d average
            if n >= 20:
                recent_vol = float(volumes.iloc[-5:].mean())
                avg_vol    = float(volumes.iloc[-20:].mean())
                if avg_vol > 0:
                    m.volume_surge = recent_vol / avg_vol

    except Exception as e:
        m.fetch_errors.append(str(e))

    return m


# ─────────────────────────────────────────────
# KEITH GILL ANALYZER
# ─────────────────────────────────────────────

def run_gill_analysis(ticker: str) -> GillAnalysis:
    g = GillAnalysis(ticker=ticker.upper())
    g.metrics = fetch_squeeze_metrics(ticker)
    m = g.metrics
    green, red = [], []

    # ── PILLAR 1: Squeeze Setup (40 pts) ──
    squeeze = 0.0
    si = m.short_interest_pct

    if si is not None:
        q = f"[{m.si_data_quality}]" if m.si_data_quality else ""
        if si >= 0.50:
            squeeze += 18
            green.append(f"Short interest {si:.1%} {q} — EXTREME. Wall Street is ALL IN on the short.")
        elif si >= 0.30:
            squeeze += 14
            green.append(f"Short interest {si:.1%} {q} — very high. Significant forced-covering risk.")
        elif si >= GILL_SHORT_INTEREST_MIN:
            squeeze += 9
            green.append(f"Short interest {si:.1%} {q} — above Gill's 20% threshold.")
        elif si >= 0.10:
            squeeze += 4
            red.append(f"Short interest {si:.1%} {q} — below 20% threshold. Mild pressure only.")
        else:
            red.append(f"Short interest {si:.1%} {q} — very low. No meaningful squeeze setup.")
    else:
        red.append("Short interest data unavailable.")

    dtc = m.days_to_cover
    if dtc is not None:
        if dtc >= 20:
            squeeze += 14
            green.append(f"DTC {dtc:.1f} days — CRITICAL. Shorts are completely trapped.")
        elif dtc >= 10:
            squeeze += 11
            green.append(f"DTC {dtc:.1f} days — very dangerous for shorts.")
        elif dtc >= GILL_DTC_MIN:
            squeeze += 7
            green.append(f"DTC {dtc:.1f} days — above 5-day threshold. Exit door is narrow.")
        elif dtc >= 2:
            squeeze += 3
            red.append(f"DTC {dtc:.1f} days — shorts can exit relatively easily.")
        else:
            red.append(f"DTC {dtc:.1f} days — shorts can cover quickly. No trap.")
    else:
        red.append("Days to cover unavailable.")

    ctb = m.ctb_proxy
    if ctb is not None:
        if ctb >= 50:
            squeeze += 8
            green.append(f"CTB proxy {ctb:.0f}% — borrow is extremely scarce.")
        elif ctb >= GILL_CTB_PROXY_MIN:
            squeeze += 5
            green.append(f"CTB proxy {ctb:.0f}% — meaningful borrow cost.")
        else:
            squeeze += 2
            red.append(f"CTB proxy {ctb:.0f}% — borrow appears available.")

    # FTD bonus — real borrow scarcity signal
    if m.ftd_pct_float and m.ftd_pct_float > 0.001:
        ftd_pct = m.ftd_pct_float
        if ftd_pct > 0.02:
            squeeze += 4
            green.append(f"FTD {ftd_pct:.2%} of float [{m.ftd_report_date}] — confirmed borrow scarcity.")
        elif ftd_pct > 0.005:
            squeeze += 2
            green.append(f"FTD {ftd_pct:.2%} of float — elevated failures to deliver.")

    g.squeeze_setup_score = min(squeeze, 44)

    # ── PILLAR 2: Fundamental Quality (35 pts) ──
    fund = 0.0
    pe = m.pe_ratio
    if pe is not None and pe > 0:
        if pe <= 10:
            fund += 10
            green.append(f"P/E {pe:.1f}x — deeply cheap. Shorts may be wrong on valuation.")
        elif pe <= 20:
            fund += 7
            green.append(f"P/E {pe:.1f}x — reasonable valuation.")
        elif pe <= GILL_PE_MAX:
            fund += 4
            red.append(f"P/E {pe:.1f}x — fair to slightly elevated.")
        else:
            red.append(f"P/E {pe:.1f}x — expensive. Shorts may have valuation right.")
    elif pe is None:
        fund += 3
        red.append("P/E unavailable — may be unprofitable.")

    rev = m.revenue_growth
    if rev is not None:
        if rev >= 0.20:
            fund += 10
            green.append(f"Revenue growing {rev:.0%} — company growing into the story.")
        elif rev >= GILL_REVENUE_GROWTH_MIN:
            fund += 6
            green.append(f"Revenue growth {rev:.0%} — positive trajectory.")
        else:
            fund += 1
            red.append(f"Revenue declining {rev:.0%} — shorts may have fundamental thesis right.")
    else:
        red.append("Revenue growth data unavailable.")

    fcf = m.free_cash_flow
    if fcf is not None:
        if fcf > 0:
            fund += 8
            green.append(f"Positive FCF ${fcf/1e6:.0f}M — real business, not burning cash.")
        else:
            fund += 1
            red.append(f"Negative FCF ${fcf/1e6:.0f}M — cash burn is a concern.")

    dte = m.debt_to_equity
    if dte is not None:
        if dte < 0.5:
            fund += 7
            green.append(f"Debt/equity {dte:.2f} — clean balance sheet.")
        elif dte < 1.5:
            fund += 4
            green.append(f"Debt/equity {dte:.2f} — manageable.")
        else:
            red.append(f"Debt/equity {dte:.2f} — heavy debt limits runway.")

    g.fundamental_score = min(fund, 35)

    # ── PILLAR 3: Catalyst (25 pts) ──
    cat = 0.0
    vs = m.volume_surge
    if vs is not None:
        if vs >= 3.0:
            cat += 12
            green.append(f"Volume surge {vs:.1f}x normal — someone is loading up.")
        elif vs >= 2.0:
            cat += 8
            green.append(f"Volume surge {vs:.1f}x normal — elevated interest.")
        elif vs >= 1.3:
            cat += 4
            green.append(f"Volume slightly elevated ({vs:.1f}x) — early signal.")
        else:
            red.append(f"Volume normal ({vs:.1f}x) — no crowd forming yet.")

    sc = m.short_change_pct
    if sc is not None:
        if sc > 0.10:
            cat += 7
            green.append(f"Short interest grew {sc:.0%} last month — shorts adding conviction. FUEL for squeeze.")
        elif sc < -0.10:
            cat += 2
            red.append(f"Short interest decreased {sc:.0%} — shorts already covering.")
        else:
            cat += 4
            green.append("Short interest stable — no capitulation yet.")

    rsi = m.rsi_14
    if rsi is not None:
        if 30 <= rsi <= 60:
            cat += 6
            green.append(f"RSI {rsi:.0f} — not overbought. Squeeze hasn't started yet.")
        elif rsi < 30:
            cat += 6
            green.append(f"RSI {rsi:.0f} — OVERSOLD. Setup building.")
        elif rsi <= 75:
            cat += 3
            red.append(f"RSI {rsi:.0f} — momentum building but watch for overextension.")
        else:
            red.append(f"RSI {rsi:.0f} — OVERBOUGHT. Squeeze may have begun or nearly over.")

    g.catalyst_score = min(cat, 25)

    g.total_score = g.squeeze_setup_score + g.fundamental_score + g.catalyst_score
    g.green_flags = green
    g.red_flags   = red

    if g.total_score >= 75:
        g.verdict, g.conviction = "SQUEEZE CANDIDATE", "YOLO"
    elif g.total_score >= 55:
        g.verdict, g.conviction = "SQUEEZE CANDIDATE", "HIGH"
    elif g.total_score >= 38:
        g.verdict, g.conviction = "WATCH", "MODERATE"
    else:
        g.verdict, g.conviction = "PASS", "LOW"

    si_str  = f"{si:.1%}" if si else "unknown"
    dtc_str = f"{dtc:.1f}" if dtc else "unknown"
    g.thesis = (
        f"{ticker.upper()} has {si_str} of float short with {dtc_str} days to cover. "
        f"Squeeze: {g.squeeze_setup_score:.0f}/44 | "
        f"Fundamental: {g.fundamental_score:.0f}/35 | "
        f"Catalyst: {g.catalyst_score:.0f}/25. "
        f"Verdict: {g.verdict} ({g.conviction} conviction)."
    )
    return g


# ─────────────────────────────────────────────
# CHAMATH ANALYZER
# ─────────────────────────────────────────────

def run_chamath_analysis(ticker: str) -> ChamathAnalysis:
    c = ChamathAnalysis(ticker=ticker.upper())
    c.metrics = fetch_squeeze_metrics(ticker)
    m = c.metrics
    green, red = [], []

    # ── PILLAR 1: Macro Setup (30 pts) ──
    macro = 0.0
    mc = m.market_cap
    if mc is not None:
        if 500e6 <= mc <= 10e9:
            macro += 12
            green.append(f"Market cap ${mc/1e9:.1f}B — ideal squeeze size.")
        elif 10e9 < mc <= 50e9:
            macro += 7
            green.append(f"Market cap ${mc/1e9:.1f}B — larger cap, needs bigger catalyst.")
        elif mc < 500e6:
            macro += 4
            red.append(f"Market cap ${mc/1e6:.0f}M — micro cap, limited liquidity.")
        else:
            red.append(f"Market cap ${mc/1e9:.0f}B — mega cap, squeeze mathematically harder.")

    ins = m.insider_ownership
    if ins is not None:
        if ins >= CHAMATH_INSIDER_THRESHOLD:
            macro += 10
            green.append(f"Insider ownership {ins:.1%} — management has skin in the game.")
        elif ins >= 0.02:
            macro += 5
            green.append(f"Insider ownership {ins:.1%} — some alignment.")
        else:
            red.append(f"Insider ownership {ins:.1%} — management not aligned.")

    inst = m.institutional_ownership
    if inst is not None:
        if 0.40 <= inst <= 0.80:
            macro += 8
            green.append(f"Institutional ownership {inst:.1%} — institutional consensus can flip rapidly.")
        elif inst > 0.80:
            macro += 4
            red.append(f"Institutional ownership {inst:.1%} — institutions ARE the short.")
        else:
            macro += 5
            green.append(f"Institutional ownership {inst:.1%} — retail can drive narrative.")

    c.macro_setup_score = min(macro, 30)

    # ── PILLAR 2: Squeeze Pressure (35 pts) ──
    pressure = 0.0
    si = m.short_interest_pct
    dtc = m.days_to_cover

    if si is not None:
        q = f"[{m.si_data_quality}]" if m.si_data_quality else ""
        if si >= 0.40:
            pressure += 18
            green.append(f"Short interest {si:.1%} {q} — maximum squeeze pressure.")
        elif si >= CHAMATH_SHORT_INTEREST_MIN:
            pressure += 12
            green.append(f"Short interest {si:.1%} {q} — meaningful. Narrative flip could cascade.")
        elif si >= 0.08:
            pressure += 5
            red.append(f"Short interest {si:.1%} {q} — modest. Needs strong catalyst.")
        else:
            red.append(f"Short interest {si:.1%} {q} — insufficient pressure.")

    if dtc is not None:
        if dtc >= 15:
            pressure += 12
            green.append(f"DTC {dtc:.1f} — catastrophically trapped.")
        elif dtc >= GILL_DTC_MIN:
            pressure += 8
            green.append(f"DTC {dtc:.1f} — tight exit. When they run, they all run at once.")
        elif dtc >= 2:
            pressure += 3
            red.append(f"DTC {dtc:.1f} — shorts can exit.")

    ctb = m.ctb_proxy
    if ctb and ctb >= GILL_CTB_PROXY_MIN:
        pressure += 5
        green.append(f"CTB proxy {ctb:.0f}% — expensive to short.")

    if m.ftd_pct_float and m.ftd_pct_float > 0.001:
        pressure += 3
        green.append(f"FTD {m.ftd_pct_float:.2%} of float — confirmed borrow scarcity.")

    c.squeeze_pressure_score = min(pressure, 35)

    # ── PILLAR 3: Catalyst Momentum (35 pts) ──
    catalyst = 0.0
    p1m = m.price_change_1m
    p3m = m.price_change_3m

    if p1m is not None:
        if p1m >= 0.30:
            catalyst += 12
            green.append(f"1-month return {p1m:.0%} — MOMENTUM IGNITED.")
        elif p1m >= CHAMATH_MOMENTUM_MIN:
            catalyst += 7
            green.append(f"1-month return {p1m:.0%} — positive momentum building.")
        elif p1m >= -0.10:
            catalyst += 3
            red.append(f"1-month return {p1m:.0%} — flat. Waiting for catalyst.")
        else:
            red.append(f"1-month return {p1m:.0%} — declining. Shorts still winning.")

    if p3m is not None:
        if p3m >= 0.50:
            catalyst += 8
            green.append(f"3-month return {p3m:.0%} — strong sustained momentum.")
        elif p3m >= 0.15:
            catalyst += 5
            green.append(f"3-month return {p3m:.0%} — trend is your friend.")
        elif p3m < -0.20:
            red.append(f"3-month return {p3m:.0%} — weak trend.")

    vs = m.volume_surge
    if vs is not None and vs >= 2.0:
        catalyst += 8
        green.append(f"Volume surge {vs:.1f}x — crowd forming.")

    sc = m.short_change_pct
    if sc is not None:
        if sc >= 0.20:
            catalyst += 7
            green.append(f"Short interest surged {sc:.0%} — shorts doubling down = more fuel.")
        elif sc <= -0.15:
            red.append(f"Short interest dropped {sc:.0%} — best entry may have passed.")
        else:
            catalyst += 3

    c.catalyst_momentum_score = min(catalyst, 35)

    c.total_score = (c.macro_setup_score +
                     c.squeeze_pressure_score +
                     c.catalyst_momentum_score)
    c.green_flags = green
    c.red_flags   = red

    if c.total_score >= 70:
        c.verdict = "SQUEEZE CANDIDATE"
    elif c.total_score >= 50:
        c.verdict = "WATCH — Building Setup"
    else:
        c.verdict = "PASS"

    si_str  = f"{si:.1%}" if si else "N/A"
    dtc_str = f"{dtc:.1f}d" if dtc else "N/A"
    mc_str  = f"${mc/1e9:.1f}B" if mc else "N/A"
    c.narrative = (
        f"Macro: {c.macro_setup_score:.0f}/30 | "
        f"Pressure: {c.squeeze_pressure_score:.0f}/35 | "
        f"Catalyst: {c.catalyst_momentum_score:.0f}/35"
    )
    c.thesis = (
        f"{ticker.upper()} ({mc_str}): SI {si_str}, DTC {dtc_str}. "
        f"Total: {c.total_score:.0f}/100 — {c.verdict}."
    )
    return c


# ─────────────────────────────────────────────
# DISPLAY FORMATTERS
# ─────────────────────────────────────────────

def format_gill_display(g: GillAnalysis) -> str:
    m = g.metrics

    def pct(v, d=1): return f"{v:.{d}%}" if v is not None else "N/A"
    def n(v, d=2):   return f"{v:.{d}f}" if v is not None else "N/A"

    # Data quality note for short interest
    si_note = f"  [{m.si_data_quality}]" if m.si_data_quality else ""

    lines = [
        "",
        f"  ── SQUEEZE SETUP ({g.squeeze_setup_score:.0f}/44) ────────────────────────────────",
        f"  Short Interest % Float:  {pct(m.short_interest_pct):<14}{si_note}",
        f"  Days to Cover (DTC):     {n(m.days_to_cover, 1):<14} threshold > 5 days",
        f"  Cost-to-Borrow Proxy:    {n(m.ctb_proxy, 1)}%       threshold > 10%",
        f"  Short Change (1mo):      {pct(m.short_change_pct):<14} (+ = shorts adding)",
        f"  FTD % of Float:          {pct(m.ftd_pct_float, 3):<14} [{m.ftd_report_date or 'no SEC data'}]",
        "",
        f"  ── FUNDAMENTAL QUALITY ({g.fundamental_score:.0f}/35) ─────────────────────────────",
        f"  P/E Ratio:               {n(m.pe_ratio, 1):<14} threshold < 30x",
        f"  Revenue Growth:          {pct(m.revenue_growth):<14} threshold > 0%",
        f"  Free Cash Flow:          {'${:,.0f}M'.format(m.free_cash_flow/1e6) if m.free_cash_flow else 'N/A':<14}",
        f"  Debt / Equity:           {n(m.debt_to_equity):<14}",
        "",
        f"  ── CATALYST SIGNALS ({g.catalyst_score:.0f}/25) ───────────────────────────────────",
        f"  Volume Surge:            {n(m.volume_surge, 1)+'x':<14} (vs 20d avg)",
        f"  RSI (14):                {n(m.rsi_14, 0):<14}",
        f"  1-Month Return:          {pct(m.price_change_1m):<14}",
        "",
        f"  ── GILL VERDICT ───────────────────────────────────────────────",
        f"  Total Score:   {g.total_score:.0f}/100",
        f"  Verdict:       {g.verdict}",
        f"  Conviction:    {g.conviction}",
        "",
        f"  GREEN FLAGS:",
    ]
    for flag in g.green_flags:
        lines.append(f"    ✅ {flag}")
    lines.append(f"  RED FLAGS:")
    for flag in g.red_flags:
        lines.append(f"    ❌ {flag}")
    lines.append("")
    return "\n".join(lines)


def format_chamath_display(c: ChamathAnalysis) -> str:
    m = c.metrics

    def pct(v, d=1): return f"{v:.{d}%}" if v is not None else "N/A"
    def n(v, d=2):   return f"{v:.{d}f}" if v is not None else "N/A"

    si_note = f"  [{m.si_data_quality}]" if m.si_data_quality else ""

    lines = [
        "",
        f"  ── MACRO SETUP ({c.macro_setup_score:.0f}/30) ──────────────────────────────────────",
        f"  Market Cap:              {'${:,.1f}B'.format(m.market_cap/1e9) if m.market_cap else 'N/A':<14}",
        f"  Insider Ownership:       {pct(m.insider_ownership):<14} threshold > 5%",
        f"  Institutional Own:       {pct(m.institutional_ownership):<14}",
        "",
        f"  ── SQUEEZE PRESSURE ({c.squeeze_pressure_score:.0f}/35) ──────────────────────────────",
        f"  Short Interest % Float:  {pct(m.short_interest_pct):<14}{si_note}",
        f"  Days to Cover (DTC):     {n(m.days_to_cover, 1):<14} threshold > 5 days",
        f"  Cost-to-Borrow Proxy:    {n(m.ctb_proxy, 1)}%",
        f"  FTD % of Float:          {pct(m.ftd_pct_float, 3):<14}",
        f"  Short Change (1mo):      {pct(m.short_change_pct):<14}",
        "",
        f"  ── CATALYST MOMENTUM ({c.catalyst_momentum_score:.0f}/35) ─────────────────────────────",
        f"  1-Month Return:          {pct(m.price_change_1m):<14}",
        f"  3-Month Return:          {pct(m.price_change_3m):<14}",
        f"  Volume Surge:            {n(m.volume_surge, 1)+'x':<14}",
        f"  RSI (14):                {n(m.rsi_14, 0):<14}",
        "",
        f"  ── CHAMATH VERDICT ─────────────────────────────────────────────",
        f"  {c.narrative}",
        f"  Total Score:   {c.total_score:.0f}/100",
        f"  Verdict:       {c.verdict}",
        "",
        f"  GREEN FLAGS:",
    ]
    for flag in c.green_flags:
        lines.append(f"    ✅ {flag}")
    lines.append(f"  RED FLAGS:")
    for flag in c.red_flags:
        lines.append(f"    ❌ {flag}")
    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "GME"
    print(f"\n{'='*60}\nKEITH GILL — {ticker.upper()}\n{'='*60}")
    gill = run_gill_analysis(ticker)
    print(format_gill_display(gill))
    print(f"\n{'='*60}\nCHAMATH — {ticker.upper()}\n{'='*60}")
    chamath = run_chamath_analysis(ticker)
    print(format_chamath_display(chamath))
