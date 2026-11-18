"""Optional, simple personal historical check; never auto-promotes a model."""
import hashlib,json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from personal_estimate import history_status
from household_model_check import load_fixed_candidate,check_history


def render_household_check(records):
    with st.expander('Check predictions against my past bills'):
        st.write('For each bill, we use only the six months before it, predict its electricity units, then compare with the actual units. Nothing is retrained or changed in your saved routine.')
        st.caption('At least 7 consecutive months gives 1 check. With 12–15 months you can get up to 6–9 checks. Missing months can reduce that number.')
        mode=st.radio('What would you like to check?',['Preview saved history','My verified bill readings'],key='household_check_mode')
        verified=False
        if mode=='My verified bill readings':
            verified=st.checkbox('I checked the saved month and units against my original bills',key='household_check_verified')
        else:st.info('Preview only. Example or unconfirmed chart readings are not proof that the model works for your home.')
        signature=hashlib.sha256(json.dumps([(r['month'],float(r['kwh'])) for r in sorted(records,key=lambda r:r['month'])]).encode()).hexdigest()
        identity=(signature,mode,verified)
        cached=st.session_state.get('household_check_result')
        if cached and cached['identity']!=identity:
            st.session_state.pop('household_check_result',None);cached=None
        if st.button('Check past predictions',disabled=not records or (mode=='My verified bill readings' and not verified)):
            try:
                bundle,metadata=load_fixed_candidate()
                with st.spinner('Checking earlier bills without retraining…'):
                    result=check_history(records,bundle,metadata['last_training_target'])
                cached=dict(identity=identity,result=result,model_hash=metadata['artifact_sha256'])
                st.session_state.household_check_result=cached
            except ValueError as error:st.error(str(error));return
        if not cached:return
        result=cached['result']
        st.caption('Input status: user-confirmed bill readings.' if verified else 'Input status: provisional preview; results are not a verified personal evaluation.')
        if not result['months_checked']:
            st.info('No eligible months to check yet. Add six earlier consecutive months plus the month whose actual bill you want to check. Check months must be later than '+result['training_cutoff']+'.')
        else:
            st.write(f"**{result['months_checked']} months checked on the same bills for every method.**")
            scores=pd.DataFrame(result['summary']).rename(columns={'method':'Method','months_checked':'Months checked','average_error_units':'Average miss (units)','rmse_units':'RMSE (units)','largest_error_units':'Largest miss (units)'})
            st.dataframe(scores[['Method','Months checked','Average miss (units)','Largest miss (units)']],hide_index=True,width='stretch')
            st.caption('Lower average miss is better. For example, a miss of 50 units means the prediction was 50 units away from the bill, not 50% accuracy. These are electricity units, not rupees.')
            if result['months_checked']<6:st.warning('Only a few months are available. Treat this as an early check, not a dependable accuracy measurement.')
            frame=pd.DataFrame(result['predictions'])
            with st.expander('See predictions month by month'):
                fig=go.Figure()
                actual=frame.drop_duplicates('month').sort_values('month')
                fig.add_trace(go.Scatter(x=actual.month,y=actual.actual_units,name='Actual bill units',mode='lines+markers',line=dict(color='#302B25',width=3)))
                for method,g in frame.groupby('method'):
                    g=g.sort_values('month');fig.add_trace(go.Scatter(x=g.month,y=g.predicted_units,name=method,mode='lines+markers',line=dict(dash='dash')))
                fig.update_layout(yaxis_title='Electricity units (kWh)',xaxis_title='Bill month',legend=dict(orientation='h'));fig.update_yaxes(rangemode='tozero')
                st.plotly_chart(fig,width='stretch')
                st.dataframe(frame[['month','method','actual_units','predicted_units','error_units']].rename(columns={'month':'Bill month','method':'Method','actual_units':'Actual units','predicted_units':'Predicted units','error_units':'Predicted minus actual'}),hide_index=True,width='stretch')
            export=frame.assign(model_sha256=cached['model_hash'],input_status='user_confirmed' if verified else 'provisional_preview',training_cutoff=result['training_cutoff'])
            st.download_button('Download this check (CSV)',export.to_csv(index=False),file_name='my_household_prediction_check.csv',mime='text/csv')
            st.info('This check does not retrain the model or change your saved estimate. The main estimate uses your selected method; these results compare historical predictions only.')
        if result['skipped']:
            with st.expander('Months that could not be checked'):
                st.dataframe(pd.DataFrame(result['skipped']).rename(columns={'month':'Month','reason':'Why it was skipped','missing_months':'Missing earlier months'}),hide_index=True,width='stretch')
        st.caption(result['notice'])
        with st.expander('Model check details'):
            st.write('Fixed Extra Trees research candidate. Latest model training target: '+result['training_cutoff']+'.')
            st.caption('Model SHA-256: '+cached['model_hash'])
            st.caption('Downloaded results stay on your computer. The check does not write extra household storage files or validate bill-price forecasts. Reusing these bills to tune a model later would make them development data.')
