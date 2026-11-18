"""Presentation only: local typography, colour and page framing."""
from pathlib import Path
import streamlit as st
PAGES={
'My bills':('YOUR HOME, IN FOCUS','Good energy starts with clarity.','All your electricity history, in one simple place. Add a bill and build a clearer picture of your home.'),
'Next bill estimate':('A LITTLE FORESIGHT','Know what’s next.','See your next month’s electricity estimate, understand your usage and plan ahead with confidence.'),
'Plan my bill':('SMALL CHANGES. SMARTER SAVINGS.','More control. Less guesswork.','Choose your budget. Explore simple changes to your daily routine and find a plan that works for you.')}

def apply_design(root):
    st.markdown('<style>'+(Path(root)/'assets/app.css').read_text()+'</style>',unsafe_allow_html=True)

def brand():
    st.sidebar.markdown('<div class="brand"><div class="brand-icon">ϟ</div><div class="brand-name">Energy<span>wise.</span></div></div><div class="brand-note">Electricity Bill Planner<br>A little insight. A lighter bill.</div>',unsafe_allow_html=True)

def page_header(view):
    kicker,title,description=PAGES[view]
    st.markdown('<div class="topline"><span>Electricity Bill Planner / '+view+'</span><span class="status-pill"><span class="status-dot"></span>Local workspace</span></div><div class="hero"><div class="hero-kicker">'+kicker+'</div><h1>'+title+'</h1><p>'+description+'</p></div>',unsafe_allow_html=True)

def footer():
    st.markdown('<div class="app-footer"><span>Energywise. · Your home, understood.</span><span>Pakistan · PKR · Estimates for planning</span></div>',unsafe_allow_html=True)
