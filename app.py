"""Local MVP: confirmed/manual history, transparent estimates and bill calculations."""
from pathlib import Path
import json,sys,os,hashlib
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from billing import calculate_bill,settings_from_bill,reconcile_example,number,editable_settings
from personal_estimate import estimate_next_month
from storage import load_records,save_records,load_settings,save_settings,StorageError,recovery_screen
from bill_photo import recognize_photo,merge_photo_record
from budget_ui import render_budget,household_estimate
from estimate_ui import render_estimate
from bills_ui import render_bills

DATA=Path(os.environ.get('ENERGY_DATA_DIR',ROOT/'data/consumer'))
st.set_page_config(page_title='Electricity Bill Planner',page_icon='💡',layout='wide')
from app_design import apply_design,brand,page_header,footer
apply_design(ROOT)
from access_ui import gate_access
DATA=gate_access(ROOT,DATA)
view=st.sidebar.radio('Go to',['My bills','Next bill estimate','Plan my bill'],key='page')
st.sidebar.markdown('<div class="sidebar-note"><strong>Your home. Your control.</strong>Keep your history together, see what’s ahead and explore ways to save.<br><br>Photos are read on this computer.</div>',unsafe_allow_html=True)
page_header(view)
try:
    records=load_records(DATA)
    settings=load_settings(DATA)
except StorageError as error:recovery_screen(error)


def breakdown(result):
    st.metric('Estimated current-period charges',f"Rs {result['total_pkr']:,.2f}")
    st.dataframe(pd.DataFrame(result['lines']).rename(columns={'name':'Charge','amount_pkr':'Amount (Rs)'}),hide_index=True,width='stretch')
    st.caption('Previous unpaid balances and late-payment fees are excluded. Displayed totals cover only the listed charges.')


def calculate(off,peak):
    return calculate_bill(off,peak,**{k:settings[k] for k in ['off_peak_rate','peak_rate','fixed_charge','phl_rate','carried_charges']})


if view=='My bills':
    records=render_bills(ROOT,DATA,records)
    with st.expander('Advanced details — bill prices and charges'):
        st.subheader('Prices and charges from your bill')
        st.write('Enter the rates printed on your bill. Other named amounts stay unchanged in scenarios until you edit them.')
        current,price_problems=editable_settings(settings)
        if settings and price_problems:st.warning('Please complete or correct: '+', '.join(price_problems)+'. Your valid saved values and bill history are kept.')
        with st.form('prices'):
            left,right=st.columns(2)
            off=left.number_input('Off-peak price per unit (Rs)',min_value=0.0,value=current.get('off_peak_rate'),format='%.4f')
            peak=right.number_input('Peak price per unit (Rs)',min_value=0.0,value=current.get('peak_rate'),format='%.4f')
            fixed=left.number_input('Fixed charge shown on your bill (Rs)',min_value=0.0,value=float(current.get('fixed_charge',0)))
            phl=right.number_input('PHL surcharge per unit, if listed (Rs)',min_value=0.0,value=float(current.get('phl_rate',0)),format='%.4f')
            charges=st.data_editor(pd.DataFrame(current.get('carried_charges',[]),columns=['name','amount_pkr']),num_rows='dynamic',hide_index=True,
                column_config={'name':'Charge name (for example FCA or sales tax)','amount_pkr':st.column_config.NumberColumn('Amount (Rs); negative for credits',format='%.2f')},key='charges_editor')
            st.caption('Keep separately named FCA, quarterly adjustments, duty, sales tax, income tax and MUCT amounts as shown. This MVP carries these amounts forward; it does not infer tax percentages or future official adjustments.')
            share=st.slider('Assumed share of future units used during peak hours (%)',0.0,100.0,float(current.get('peak_share',0.1))*100,step=0.1)
            st.caption('If loaded from your example, the starting share comes from October’s measured peak/off-peak split. It may change next month.')
            start=left.text_input('Peak hours start (24-hour HH:MM)',value=current.get('peak_start','17:30'))
            end=right.text_input('Peak hours end (24-hour HH:MM)',value=current.get('peak_end','22:30'))
            if st.form_submit_button('Save prices and assumptions'):
                try:
                    from datetime import datetime
                    datetime.strptime(start,'%H:%M');datetime.strptime(end,'%H:%M')
                    if start==end:raise ValueError('Peak start and end times must differ.')
                    extra=[]
                    for r in charges.to_dict('records'):
                        if pd.isna(r.get('name')) and pd.isna(r.get('amount_pkr')):continue
                        name=str(r['name']).strip()
                        if not name or name=='nan':raise ValueError('Give every charge a name.')
                        extra.append(dict(name=name,amount_pkr=float(number(r['amount_pkr'],name,True))))
                    saved=dict(off_peak_rate=float(number(off,'Off-peak rate')),peak_rate=float(number(peak,'Peak rate')),
                        fixed_charge=fixed,phl_rate=phl,carried_charges=extra,peak_share=share/100,
                        peak_start=start,peak_end=end,source_month=current.get('source_month','User entered'))
                    saved['forecast_method']=current.get('forecast_method','extra_trees')
                    for key in ('forecast_method','billing_scope'):
                        if key in current:saved[key]=current[key]
                    save_settings(DATA,saved);st.success('Prices saved.');st.rerun()
                except (ValueError,KeyError) as error:st.error(str(error))

elif view=='Next bill estimate':
    render_estimate(records,settings,DATA)

else:
    render_budget(DATA,records,settings)

footer()
