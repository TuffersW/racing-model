import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Racing EV Finder", page_icon="🏇", layout="wide")

st.title("🏇 Racing EV Finder")
st.markdown("Enter race data to compare model prices vs market odds and find value bets.")

# Sidebar
st.sidebar.header("Settings")
min_ev = st.sidebar.slider("Minimum EV threshold (%)", 1, 15, 3)
bankroll = st.sidebar.number_input("Bankroll ($)", 100, 100000, 1000)
kelly_fraction = st.sidebar.slider("Kelly fraction", 0.1, 1.0, 0.25)

st.sidebar.markdown("---")
st.sidebar.markdown("""
**How it works:**
- Enter each runner's details
- Model calculates fair odds based on form, barrier, weight, class
- Compares to market odds to find +EV bets
""")

# Functions
def calculate_form_score(form_string):
    """Convert form string to score (lower positions = better)."""
    if not form_string:
        return 50
    positions = [int(c) for c in form_string if c.isdigit()]
    if not positions:
        return 50
    weights = [0.5 ** i for i in range(len(positions))]
    scores = [max(0, 100 - (p - 1) * 12) for p in positions]
    return sum(s * w for s, w in zip(scores, weights)) / sum(weights)

def calculate_barrier_score(barrier, field_size, distance):
    """Score barrier advantage."""
    relative = barrier / field_size
    multiplier = 1.5 if distance < 1200 else 1.0 if distance < 1600 else 0.6
    return (1 - relative * 0.4) * multiplier * 50

def calculate_weight_score(weight, field_avg_weight):
    """Lighter weight = advantage."""
    diff = field_avg_weight - weight
    return 50 + diff * 5

def calculate_class_score(win_percentage):
    """Higher win % = higher class."""
    return win_percentage * 100

def generate_model_prices(runners_df, distance):
    """Generate model probabilities and prices."""
    scores = []
    field_avg_weight = runners_df['weight'].mean()
    field_size = len(runners_df)
    
    for _, r in runners_df.iterrows():
        form = calculate_form_score(r['form'])
        barrier = calculate_barrier_score(r['barrier'], field_size, distance)
        weight = calculate_weight_score(r['weight'], field_avg_weight)
        class_score = calculate_class_score(r.get('win_pct', 10))
        
        # Weighted combination
        total = (form * 0.35) + (barrier * 0.15) + (weight * 0.15) + (class_score * 0.35)
        scores.append(total)
    
    # Convert to probabilities
    scores = np.array(scores)
    scores = np.maximum(scores, 1)  # Floor
    probs = scores / scores.sum()
    prices = 1 / probs
    
    return probs, prices

# Main input
st.header("Race Details")

col1, col2, col3 = st.columns(3)
track = col1.text_input("Track", "Randwick")
distance = col2.number_input("Distance (m)", 800, 3200, 1200, step=100)
condition = col3.selectbox("Condition", ["Good", "Firm", "Soft", "Heavy"])

st.markdown("---")
st.header("Runners")
st.markdown("Enter details for each runner. **Form** = last 5 finishing positions (e.g., '21435').")

num_runners = st.number_input("Number of runners", 2, 24, 8)

# Input grid
data = []
cols = st.columns([2.5, 1, 1, 1.5, 1.5, 1.5])
cols[0].markdown("**Horse**")
cols[1].markdown("**Barrier**")
cols[2].markdown("**Weight**")
cols[3].markdown("**Form**")
cols[4].markdown("**Win %**")
cols[5].markdown("**Market Odds**")

for i in range(int(num_runners)):
    cols = st.columns([2.5, 1, 1, 1.5, 1.5, 1.5])
    horse = cols[0].text_input(f"h{i}", key=f"horse_{i}", label_visibility="collapsed", placeholder=f"Runner {i+1}")
    barrier = cols[1].number_input(f"b{i}", 1, 24, i+1, key=f"bar_{i}", label_visibility="collapsed")
    weight = cols[2].number_input(f"w{i}", 50.0, 65.0, 57.0, step=0.5, key=f"wt_{i}", label_visibility="collapsed")
    form = cols[3].text_input(f"f{i}", "55555", key=f"form_{i}", label_visibility="collapsed")
    win_pct = cols[4].number_input(f"wp{i}", 0.0, 50.0, 10.0, step=1.0, key=f"win_{i}", label_visibility="collapsed")
    odds = cols[5].number_input(f"o{i}", 1.01, 501.0, 5.0, step=0.1, key=f"odds_{i}", label_visibility="collapsed")
    
    if horse:
        data.append({
            'horse': horse,
            'barrier': barrier,
            'weight': weight,
            'form': form,
            'win_pct': win_pct,
            'market_odds': odds
        })

st.markdown("---")

# Analyse button
if st.button("🎯 Find Value Bets", type="primary", use_container_width=True):
    if len(data) < 2:
        st.error("Enter at least 2 runners with names")
    else:
        df = pd.DataFrame(data)
        
        # Generate model prices
        probs, prices = generate_model_prices(df, distance)
        
        df['model_prob'] = probs
        df['model_price'] = prices
        df['market_prob'] = 1 / df['market_odds']
        df['ev_pct'] = (df['model_prob'] - df['market_prob']) * 100
        df['ev_roi'] = (df['model_prob'] * df['market_odds'] - 1) * 100
        
        # Kelly stake
        df['kelly'] = df.apply(
            lambda r: max(0, r['ev_roi'] / 100 / (r['market_odds'] - 1)) * kelly_fraction 
            if r['ev_roi'] > 0 else 0, axis=1
        )
        df['stake'] = (df['kelly'] * bankroll).round(2)
        
        df['is_value'] = df['ev_pct'] >= min_ev
        df = df.sort_values('ev_pct', ascending=False)
        
        # Results
        st.header("📊 Results")
        
        value_bets = df[df['is_value']]
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Runners", len(df))
        c2.metric("Value Bets", len(value_bets))
        c3.metric("Best EV", f"{df['ev_pct'].max():.1f}%")
        c4.metric("Total Stake", f"${value_bets['stake'].sum():.0f}")
        
        st.markdown("---")
        
        # Value bets
        if len(value_bets) > 0:
            st.subheader("🎯 Value Bets")
            for _, r in value_bets.iterrows():
                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
                col1.markdown(f"### {r['horse']}")
                col2.metric("Model Price", f"${r['model_price']:.2f}")
                col3.metric("Market Odds", f"${r['market_odds']:.2f}")
                col4.metric("Edge", f"+{r['ev_pct']:.1f}%")
                col5.metric("Stake", f"${r['stake']:.0f}")
            st.markdown("---")
        else:
            st.info(f"No value bets found above {min_ev}% threshold")
        
        # Full table
        st.subheader("Full Field")
        
        display = df[['horse', 'barrier', 'model_price', 'market_odds', 'ev_pct', 'ev_roi', 'stake']].copy()
        display.columns = ['Horse', 'Bar', 'Model $', 'Market $', 'EV %', 'ROI %', 'Stake $']
        display['Model $'] = display['Model $'].round(2)
        display['EV %'] = display['EV %'].round(1)
        display['ROI %'] = display['ROI %'].round(1)
        
        st.dataframe(display, use_container_width=True, hide_index=True)
        
        # Download
        csv = df.to_csv(index=False)
        st.download_button("📥 Download CSV", csv, f"{track}_analysis.csv", "text/csv")

st.markdown("---")
st.caption("Model estimates only. Gamble responsibly.")
