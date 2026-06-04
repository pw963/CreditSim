import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from dataclasses import dataclass
from typing import List
import math
 
# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Credit Score Simulator | FEC Paterson",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&display=swap');
 
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
 
h1, h2, h3 { font-family: 'DM Serif Display', serif !important; }
 
.main { background: #f7f4ef; }
.block-container { padding-top: 2rem; }
 
/* Score badge */
.score-badge {
    background: linear-gradient(135deg, #1a3a2a, #2d6a4f);
    color: white;
    border-radius: 20px;
    padding: 2rem 2.5rem;
    text-align: center;
    margin-bottom: 1rem;
}
.score-number { font-size: 4.5rem; font-family: 'DM Serif Display', serif; line-height: 1; }
.score-label { font-size: 0.9rem; opacity: 0.8; text-transform: uppercase; letter-spacing: 1px; }
.score-range { font-size: 1.1rem; font-weight: 600; margin-top: 0.3rem; }
 
/* Outcome cards */
.outcome-card {
    background: white;
    border-radius: 16px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 0.75rem;
    border-left: 5px solid #2d6a4f;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.outcome-card.positive { border-left-color: #2d6a4f; }
.outcome-card.neutral  { border-left-color: #e9c46a; }
.outcome-card.negative { border-left-color: #e76f51; }
 
.outcome-title { font-weight: 600; font-size: 0.9rem; color: #1a3a2a; }
.outcome-pts   { font-size: 1.6rem; font-family: 'DM Serif Display', serif; }
.outcome-pts.pos { color: #2d6a4f; }
.outcome-pts.neg { color: #e76f51; }
 
/* Header strip */
.fec-header {
    background: #1a3a2a;
    color: white;
    padding: 1rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
 
/* Metric pill */
.pill {
    display: inline-block;
    background: #e8f5e9;
    color: #1a3a2a;
    border-radius: 50px;
    padding: 0.25rem 0.75rem;
    font-size: 0.82rem;
    font-weight: 600;
    margin: 0.2rem;
}
 
/* Tip box */
.tip-box {
    background: #fffbf0;
    border: 1px solid #e9c46a;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-top: 0.5rem;
    font-size: 0.9rem;
}
</style>
""", unsafe_allow_html=True)
 
 
# ── Credit score model ────────────────────────────────────────────────────────
# FICO approximate weights:
# Payment history     35 %
# Credit utilization  30 %
# Length of history   15 %
# Credit mix          10 %
# New credit          10 %
 
SCORE_BANDS = [
    (800, 850, "Exceptional",  "#2d6a4f"),
    (740, 799, "Very Good",    "#52b788"),
    (670, 739, "Good",         "#e9c46a"),
    (580, 669, "Fair",         "#f4a261"),
    (300, 579, "Poor",         "#e76f51"),
]
 
def score_band(score: int):
    for lo, hi, label, color in SCORE_BANDS:
        if lo <= score <= hi:
            return label, color
    return "Unknown", "#aaa"
 
 
def clamp(val, lo, hi):
    return max(lo, min(hi, val))
 
 
def simulate_score(
    current_score: int,
    months: int,
    # Payment history actions
    on_time_streak: int,          # consecutive months of on-time payments already
    missed_payments_next: int,    # planned missed payments over period
    # Utilization
    current_util: float,          # 0–100 %
    target_util: float,           # goal utilization
    # History length
    avg_account_age_years: float,
    # Credit mix
    num_credit_cards: int,
    has_installment_loan: bool,
    # New credit
    hard_inquiries: int,
    new_accounts: int,
    # Recovery
    has_collection: bool,
    paying_off_collection: bool,
) -> List[int]:
    """Return list of projected scores for each month."""
    scores = [current_score]
    score = float(current_score)
 
    util_improvement_per_month = (current_util - target_util) / max(months, 1)
    current_util_now = current_util
 
    for m in range(1, months + 1):
        delta = 0.0
 
        # 1. Payment history (35%) — on-time streak boosts, missed payments hurt hard
        if missed_payments_next == 0:
            streak_bonus = min((on_time_streak + m) / 24, 1.0)  # max after 2 yrs
            delta += 0.35 * streak_bonus * 1.8
        else:
            # Distribute missed payments roughly
            if m <= missed_payments_next:
                delta -= 0.35 * 12  # ~-12 pts/month for each miss
 
        # 2. Utilization (30%) — linear improvement toward target
        current_util_now = max(target_util, current_util_now - util_improvement_per_month)
        util_score_factor = 1.0 - (current_util_now / 100)
        ideal_factor = 1.0 - (target_util / 100)
        util_delta = (ideal_factor - (1.0 - current_util / 100)) * 0.30 * 80
        delta += util_delta * (m / months)  # ramp up over time
 
        # 3. Length of history (15%) — slow steady gain from aging accounts
        age_gain = 0.15 * 0.3 * (1 / 12)  # tiny per month
        delta += age_gain
 
        # 4. Credit mix (10%)
        mix_score = 0
        if num_credit_cards >= 1: mix_score += 5
        if num_credit_cards >= 2: mix_score += 3
        if has_installment_loan:   mix_score += 5
        delta += 0.10 * mix_score * 0.05
 
        # 5. Hard inquiries / new accounts (10%) — fade after 12 months
        if m <= 12:
            inquiry_penalty = hard_inquiries * 4 * ((12 - m) / 12)
            new_acct_penalty = new_accounts * 3 * ((12 - m) / 12)
            delta -= 0.10 * (inquiry_penalty + new_acct_penalty) / 12
 
        # 6. Collections
        if has_collection and not paying_off_collection:
            delta -= 0.5  # drag every month
        elif has_collection and paying_off_collection and m > 3:
            delta += 0.8  # starts recovering after 3 months
 
        score = clamp(score + delta, 300, 850)
        scores.append(round(score))
 
    return scores
 
 
# ── Sidebar inputs ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 Client Profile")
    st.markdown("---")
 
    current_score = st.slider("Current Credit Score", 300, 850, 580, 5)
    months = st.selectbox("Projection Period", [6, 12, 18, 24], index=1, format_func=lambda x: f"{x} months")
 
    st.markdown("### 💳 Payment History")
    on_time_streak = st.number_input("Consecutive on-time months so far", 0, 120, 3)
    missed_payments_next = st.number_input("Planned missed payments in this period", 0, 12, 0)
 
    st.markdown("### 📊 Credit Utilization")
    current_util = st.slider("Current utilization %", 0, 100, 72)
    target_util = st.slider("Target utilization %", 0, 100, 25)
    if target_util > current_util:
        target_util = current_util
        st.warning("Target can't be higher than current utilization.")
 
    st.markdown("### 🏦 Credit Mix & History")
    avg_age = st.number_input("Avg account age (years)", 0.0, 30.0, 2.5, 0.5)
    num_cards = st.number_input("Number of credit cards", 0, 10, 1)
    has_loan = st.checkbox("Has installment loan (auto, student, personal)", value=False)
 
    st.markdown("### 🔍 New Credit Activity")
    hard_inquiries = st.number_input("Hard inquiries planned", 0, 10, 0)
    new_accounts = st.number_input("New accounts planned", 0, 10, 0)
 
    st.markdown("### ⚠️ Collections")
    has_collection = st.checkbox("Has a collection account", value=False)
    paying_off_collection = False
    if has_collection:
        paying_off_collection = st.checkbox("Planning to pay off collection", value=False)
 
 
# ── Simulate ───────────────────────────────────────────────────────────────────
scores = simulate_score(
    current_score, months,
    on_time_streak, missed_payments_next,
    current_util, target_util,
    avg_age, num_cards, has_loan,
    hard_inquiries, new_accounts,
    has_collection, paying_off_collection,
)
 
final_score = scores[-1]
start_band, start_color = score_band(current_score)
end_band, end_color = score_band(final_score)
delta_score = final_score - current_score
 
 
# ── Main layout ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="fec-header">
  <div>
    <span style="font-family:'DM Serif Display',serif;font-size:1.4rem;">
      FEC Paterson · Credit Score Simulator - v1.0
    </span>
    <br><span style="opacity:0.7;font-size:0.85rem;">
      Financial Empowerment Center — v1.0
    </span>
  </div>
  <div style="text-align:right;opacity:0.8;font-size:0.8rem;">
    Free financial counseling for Paterson residents<br>
    By: Gerd Pflucker
    
  </div>
</div>
""", unsafe_allow_html=True)
 

col_score, col_chart = st.columns([1, 2.4])
 
with col_score:
    arrow = "▲" if delta_score >= 0 else "▼"
    sign  = "+" if delta_score >= 0 else ""
    color = "#52b788" if delta_score >= 0 else "#e76f51"
 
    st.markdown(f"""
    <div class="score-badge">
      <div class="score-label">Projected score in {months} months</div>
      <div class="score-number">{final_score}</div>
      <div class="score-range" style="color:{end_color};">{end_band}</div>
      <div style="margin-top:0.8rem;font-size:1.1rem;color:{color};">
        {arrow} {sign}{delta_score} pts from {current_score}
      </div>
    </div>
    """, unsafe_allow_html=True)
 
    # Band breakdown pill labels
    st.markdown("**Score Ranges**")
    for lo, hi, label, c in SCORE_BANDS:
        bullet = "◀ you'll be here" if lo <= final_score <= hi else ""
        st.markdown(f'<span class="pill" style="background:{c}22;color:{c};border:1px solid {c}55;">{lo}–{hi} {label}</span> <small>{bullet}</small>', unsafe_allow_html=True)
 
with col_chart:
    month_labels = [f"Mo {i}" for i in range(len(scores))]
    month_labels[0] = "Now"
 
    fig = go.Figure()
 
    # Fill area
    fig.add_trace(go.Scatter(
        x=month_labels, y=scores,
        fill='tozeroy',
        fillcolor='rgba(45,106,79,0.08)',
        line=dict(color='#2d6a4f', width=3),
        mode='lines+markers',
        marker=dict(size=6, color='#2d6a4f'),
        name='Projected Score',
        hovertemplate='Month %{x}<br>Score: <b>%{y}</b><extra></extra>',
    ))
 
    # Band reference lines
    for lo, hi, label, c in SCORE_BANDS:
        fig.add_hline(y=lo, line_dash="dot", line_color=c, opacity=0.4,
                      annotation_text=label, annotation_position="right",
                      annotation_font_color=c, annotation_font_size=11)
 
    fig.update_layout(
        title=dict(text=f"Credit Score Trajectory — {months}-Month Projection", font_size=16, font_family="DM Serif Display"),
        xaxis_title="Month",
        yaxis_title="Credit Score",
        yaxis=dict(range=[max(300, min(scores)-40), min(870, max(scores)+40)]),
        plot_bgcolor='white',
        paper_bgcolor='#f7f4ef',
        font_family="DM Sans",
        showlegend=False,
        margin=dict(t=50, b=40, l=10, r=80),
        height=360,
    )
    st.plotly_chart(fig, width="stretch")
 
 
# ── Action breakdown ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### What's Driving Your Score")
 
col1, col2, col3 = st.columns(3)
 
def impact_card(title, pts, note, col):
    sign = "+" if pts >= 0 else ""
    cls = "positive" if pts > 0 else ("negative" if pts < 0 else "neutral")
    pcls = "pos" if pts >= 0 else "neg"
    col.markdown(f"""
    <div class="outcome-card {cls}">
      <div class="outcome-title">{title}</div>
      <div class="outcome-pts {pcls}">{sign}{pts} pts</div>
      <div style="font-size:0.82rem;color:#555;margin-top:0.3rem;">{note}</div>
    </div>
    """, unsafe_allow_html=True)
 
# Estimate component impacts
payment_impact = round(-missed_payments_next * 85 + min(on_time_streak + months, 24) / 24 * 35)
util_impact = round((current_util - target_util) * 0.7) if target_util < current_util else 0
collection_impact = round(25 if (has_collection and paying_off_collection) else (-18 if has_collection else 0))
inquiry_impact = round(-hard_inquiries * 5 - new_accounts * 4)
mix_impact = round((3 if has_loan else 0) + min(num_cards, 2) * 2)
 
impact_card("Payment History (35%)", payment_impact,
            "On-time payments are the #1 factor. Every missed payment hurts for 7 years.", col1)
impact_card("Credit Utilization (30%)", util_impact,
            f"Going from {current_util}% → {target_util}% utilization. Keep it under 30%.", col1)
impact_card("Account Age (15%)", 5,
            "Older accounts = better. Don't close old cards — even unused ones.", col2)
impact_card("Credit Mix (10%)", mix_impact,
            "Having both revolving (cards) and installment (loans) helps.", col2)
impact_card("New Credit (10%)", inquiry_impact,
            f"{hard_inquiries} hard inquiries + {new_accounts} new accounts. Each fades after 12 months.", col3)
impact_card("Collections", collection_impact,
            "Paying off a collection can recover 20–40 pts over 6–12 months." if has_collection else "No collections — great foundation.", col3)
 
 
# ── Personalized tips ──────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 💡 Counselor Action Plan")
 
tips = []
 
if current_util > 30:
    tips.append(("🎯 Priority: Lower Your Utilization",
                 f"You're at {current_util}% utilization. Getting below 30% can add 20–50 pts. "
                 f"Pay down the card with the highest balance first (avalanche method)."))
 
if missed_payments_next > 0:
    tips.append(("⚠️ Avoid Missed Payments",
                 "A single missed payment can drop your score 80–110 pts and stays on your report for 7 years. "
                 "Set up autopay for at least the minimum due."))
 
if on_time_streak < 12:
    tips.append(("📅 Build Your On-Time Streak",
                 f"You've made {on_time_streak} consecutive on-time payments. "
                 "Getting to 12 months straight gives a meaningful boost. Consistency is key."))
 
if has_collection and not paying_off_collection:
    tips.append(("📞 Address Collection Accounts",
                 "Collections drag your score every month. Contact the collector to negotiate a "
                 "'pay-for-delete' agreement — some collectors will remove the item entirely."))
 
if num_cards == 0:
    tips.append(("💳 Consider a Secured Credit Card",
                 "A secured card (you deposit $200–500 as collateral) is the fastest way to build credit "
                 "from scratch. Use it for small purchases and pay it off monthly."))
 
if not has_loan and num_cards >= 1:
    tips.append(("🏦 Diversify Your Credit Mix",
                 "A small credit-builder loan from a credit union can add installment history, "
                 "which makes up 10% of your score."))
 
if not tips:
    tips.append(("✅ You're On the Right Track",
                 "Keep paying on time, keep utilization low, and avoid opening too many new accounts at once. "
                 "Time and consistency are your best tools now."))
 
for title, body in tips:
    st.markdown(f"""
    <div class="tip-box">
      <strong>{title}</strong><br>{body}
    </div>
    """, unsafe_allow_html=True)
 
# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align:center;color:#888;font-size:0.8rem;padding:1rem;">
  This simulator is for educational purposes and uses approximate FICO modeling.
  Results are projections, not guarantees. For a free personal counseling session:<br>
  <strong>By Gerd Pflucker | Working on realistic formula manipulation for FICO inputs.</strong>
            
</div>
""", unsafe_allow_html=True)
 