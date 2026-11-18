"""Plain-language forecast page, with observed consumption separate from estimates."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from personal_estimate import history_status,MIN_MONTHS
from budget_ui import household_estimate
from budget_planner import bill_for_units
from consumer_forecast import combined_prices_pending


def render_estimate(records,settings,data=None):
    st.subheader('Your next bill estimate')
    try:status=history_status(records)
    except ValueError as error:st.error(str(error));return
    from history_help_ui import missing_household_reading
    repair=missing_household_reading(records,data,settings) if data is not None else False
    count=status['consecutive']
    st.caption(f'{status["total"]} months recorded · {count} consecutive months ending with your latest bill')
    st.progress(min(count/MIN_MONTHS,1.),text=f'{min(count,MIN_MONTHS)} of {MIN_MONTHS} months needed to start · 12 months recommended')
    if status['missing'] and not repair:
        st.warning('Missing months needed to proceed: '+', '.join(status['missing']))
    if not status['ready'] and not repair:
        st.info('Add at least six consecutive monthly records to unlock the next-bill estimate and target-bill plan. You can continue uploading and reviewing bills now.')
    if (settings or {}).get('forecast_method')=='extra_trees':
        st.caption('Your electricity use is predicted with the tested Extra Trees model.' if status['ready'] else 'Add the missing readings to start your prediction.')
    if combined_prices_pending(settings):
        st.info('The money calculator also needs an update for your two meters. This is work for us to finish; you do not need to change any prices now.')
    estimate=None;amount=None
    if status['ready']:
        try:estimate=household_estimate(records,settings)
        except ValueError as error:st.error(str(error));return
        units=estimate['consumption_kwh']
        left,right=st.columns(2)
        if settings and not combined_prices_pending(settings):
            try:amount=bill_for_units(units,settings)['total_pkr']
            except ValueError as error:st.error(str(error))
        if amount is not None:left.metric('Estimated next bill',f'Rs {amount:,.2f}')
        elif not combined_prices_pending(settings):left.info('Add bill prices in My bills to see the estimated cost.')
        right.metric('Estimated electricity use',f'{units:,.1f} units')
        st.caption(f'Estimate for {estimate["target_month"]}. '+('Includes your accepted appliance plan.' if estimate.get('saved_plan') else estimate['method']+'.'))
        latest=max(records,key=lambda r:r['month'])
        difference=units-float(latest['kwh'])
        st.write(f'Compared with {latest["month"]}: about {abs(difference):.1f} units '+('more.' if difference>=0 else 'less.'))
        st.caption('Previous bill amounts have not been recorded as a monthly series, so a real rupee-to-rupee bill comparison is not shown.')
        def open_planner():st.session_state.page='Plan my bill'
        if not combined_prices_pending(settings):st.button('Plan for a lower bill',type='primary',on_click=open_planner)
    if records:
        st.subheader('Your electricity use over time')
        rows=sorted(records,key=lambda r:r['month'])
        # Calendar dates preserve visible gaps; do not draw through missing months.
        frame=pd.DataFrame(rows);frame['date']=pd.to_datetime(frame['month']+'-01')
        series=frame.set_index('date')['kwh'].reindex(pd.date_range(frame['date'].min(),frame['date'].max(),freq='MS'))
        figure=go.Figure(go.Scatter(x=series.index,y=series.values,name='Recorded electricity use',mode='lines+markers',connectgaps=False,line=dict(color='#0071E3')))
        if estimate:
            figure.add_trace(go.Scatter(x=[pd.Timestamp(estimate['target_month']+'-01')],y=[estimate['consumption_kwh']],name='Next-month estimate',mode='markers',marker=dict(symbol='diamond-open',size=14,color='#248A64')))
        figure.update_layout(paper_bgcolor='white',plot_bgcolor='white',font=dict(family='-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',color='#6E6E73'),yaxis_title='Electricity units (kWh)',xaxis_title='Bill month',legend=dict(orientation='h'),margin=dict(l=10,r=10,t=15,b=10))
        figure.update_xaxes(showgrid=False);figure.update_yaxes(rangemode='tozero',gridcolor='#ECECF0',zeroline=False);st.plotly_chart(figure,width='stretch')
        st.caption('The chart shows your saved electricity use.' + (' The diamond shows next month’s estimate.' if estimate else ' No next-month estimate has been made yet.'))
    with st.expander('What could change this estimate?'):
        st.write('Using AC more, visitors, time away from home or new appliances can change your electricity use. The current estimate does not automatically know these changes.')
        st.write('Prices, fuel adjustments and taxes can also change. The saved named amounts are carried forward until edited. Previous unpaid balances and late-payment charges are excluded.')
    with st.expander('Calculation details'):
        st.write('Six consecutive months are required to start; 12 months are recommended. The selected method uses your recorded consumption history. Requiring six months does not itself establish accuracy.')
        if estimate:
            st.write('Input months: '+', '.join(estimate['source_months']))
            st.caption(estimate['notice'])
            if amount is not None:st.dataframe(pd.DataFrame(bill_for_units(estimate['consumption_kwh'],settings)['lines']),hide_index=True)
        st.write('The French-household model is not used for your personal bill. No accuracy percentage or uncertainty range has been established yet.')
    from household_check_ui import render_household_check
    render_household_check(records)
