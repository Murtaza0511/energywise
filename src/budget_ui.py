"""Plain-language household budget workflow."""
import calendar,uuid,hashlib,json
import streamlit as st
import pandas as pd
from budget_planner import PRESETS,suggest_plans,bill_for_units,automatic_choices,savings_options
from storage import load_appliances,save_appliances,save_settings,StorageError,recovery_screen,plan_transaction
from personal_estimate import validate_saved_plan
from consumer_forecast import forecast,combined_prices_pending


def history_signature(records):
    return hashlib.sha256(json.dumps(sorted([(r['month'],float(r['kwh'])) for r in records]),sort_keys=True).encode()).hexdigest()


def household_estimate(records,settings):
    result=forecast(records,settings)
    plan=(settings or {}).get('saved_usage_plan')
    if settings and 'saved_usage_plan' in settings:validate_saved_plan(plan)
    if plan and plan['history_signature']==history_signature(records):
        result['plan_model_outdated']=plan.get('inference_sha256')!=result.get('inference_sha256')
        result['consumption_kwh']=plan['units']
        result['saved_plan']=True
    return result


def time_label(hours):
    minutes=round(hours*60)
    h,m=divmod(minutes,60)
    return f'{h}h {m:02d}m'


def clear_plan(data,settings):
    if settings and 'saved_usage_plan' in settings:
        updated=dict(settings);updated.pop('saved_usage_plan');save_settings(data,updated)

def save_routine(data,rows,settings,usage_changed=True):
    if usage_changed and settings and 'saved_usage_plan' in settings:
        with plan_transaction(data):
            save_appliances(data,rows);clear_plan(data,settings)
    else:save_appliances(data,rows)


def render_budget(data,records,settings):
    st.subheader('What would you like your next bill to be?')
    if combined_prices_pending(settings):
        st.info('Your history now includes both meters. Their separate prices and charges must be connected before calculating a combined rupee target. Your saved appliance routine is kept.');return
    if not settings:
        st.info('First add your bill prices in My bills, or load your supplied examples there.');return
    try:estimate=household_estimate(records,settings)
    except ValueError as error:
        st.error(str(error));return
    units=estimate['consumption_kwh']
    year,month=map(int,estimate['target_month'].split('-'));days=calendar.monthrange(year,month)[1]
    try:starting=bill_for_units(units,settings)
    except ValueError as error:
        st.error(str(error));return
    st.metric(f"Your estimated next bill · {estimate['target_month']}",f"Rs {starting['total_pkr']:,.2f}")
    st.caption('Based on your saved usage plan.' if estimate.get('saved_plan') else 'Starting estimate: '+estimate['method']+'.')
    target=st.number_input('I want my bill to be around (Rs)',min_value=0.,value=25000.,step=500.,key='bill_target')
    st.write('Tell us once what you use at home. Enter your target and we will suggest what to use less.')
    try:appliances=load_appliances(data)
    except StorageError as error:recovery_screen(error)
    with st.expander('Add an appliance',expanded=not appliances):
        kind=st.selectbox('What appliance is it?',list(PRESETS),key='appliance_kind')
        with st.form('new_appliance'):
            name=st.text_input('Name (optional)',placeholder='For example: bedroom AC')
            quantity=st.number_input('How many?',min_value=1,max_value=100,value=1,step=1)
            hours=st.number_input('Hours used per day',min_value=.25,max_value=24.,value=4.,step=.25)
            week=st.number_input('Days used per week',min_value=1,max_value=7,value=7,step=1)
            with st.expander('Estimated power — optional details'):
                st.caption('An approximate starting value, not a measurement of your appliance. AC power varies with temperature, settings and compressor cycling.')
                watts=st.number_input('Power in watts (change only if you know it)',min_value=1.,value=PRESETS[kind],key=f'watts_{kind}')
            if st.form_submit_button('Add to my routine'):
                row=dict(id=uuid.uuid4().hex,name=name.strip() or kind,kind=kind,quantity=quantity,hours=hours,days=week,can_reduce=True,minimum_hours=hours/2,watts=watts)
                try:
                    save_routine(data,[*appliances,row],settings);st.rerun()
                except StorageError as error:recovery_screen(error)
                except (ValueError,OSError) as error:st.error('Your routine could not be saved. '+str(error))
    if appliances:
        st.subheader('What you normally use')
        st.caption('Enter your usual routine here. The app will choose which appliances to suggest reducing.')
        frame=pd.DataFrame([{'id':r['id'],'name':r['name'],'quantity':r['quantity'],'hours':r['hours'],'days':r['days']} for r in appliances])
        with st.form('edit_routine'):
            edited=st.data_editor(frame,hide_index=True,width='stretch',disabled=['id'],column_config={
                'id':None,'name':'Appliance','quantity':st.column_config.NumberColumn('How many',min_value=1,step=1),
                'hours':st.column_config.NumberColumn('Hours/day',min_value=0.,max_value=24.),
                'days':st.column_config.NumberColumn('Days/week',min_value=1,max_value=7,step=1)})
            if st.form_submit_button('Save my usual routine'):
                try:
                    originals={r['id']:r for r in appliances}
                    rows=[dict(originals[r['id']],**r,minimum_hours=min(originals[r['id']]['minimum_hours'],r['hours'])) for r in edited.to_dict('records')]
                    if rows==appliances:st.success('Your routine is already saved. Your accepted plan has been kept.')
                    else:
                        changed=any(any(r[k]!=originals[r['id']][k] for k in ('quantity','hours','days')) for r in rows)
                        save_routine(data,rows,settings,changed);st.rerun()
                except StorageError as error:recovery_screen(error)
                except (ValueError,OSError) as error:st.error('Your routine could not be saved. '+str(error))
        with st.expander('Remove an appliance'):
            remove=st.selectbox('Choose an appliance to remove',[r['id'] for r in appliances],format_func=lambda key:next(r['name'] for r in appliances if r['id']==key))
            if st.button('Remove selected appliance'):
                try:save_routine(data,[r for r in appliances if r['id']!=remove],settings);st.rerun()
                except StorageError as error:recovery_screen(error)
                except (ValueError,OSError) as error:st.error('Your routine could not be saved. '+str(error))
    else:st.info('Add your first appliance above. You do not need to know its watts.')
    if appliances and st.button('Show me how',type='primary'):
        st.session_state.show_budget_suggestions=True
    if appliances and st.session_state.get('show_budget_suggestions',False):
        st.caption('Compare three ways to use less electricity. Larger savings mean bigger cuts in daily hours. Every appliance keeps some usage time. Nothing is saved until you accept a plan.')
        suggestions=st.container()
        with st.expander('These changes do not suit me — adjust suggestions'):
            protected=st.multiselect('Keep these appliances unchanged',[r['id'] for r in appliances],format_func=lambda key:next(r['name'] for r in appliances if r['id']==key),key='protected_appliances')
            limits={}
            for row in appliances:
                limits[row['id']]=st.number_input(f"Keep at least this many hours per day: {row['name']}",min_value=min(float(row['hours']),max(1/60,float(row['hours'])*.1)),max_value=float(row['hours']),value=min(float(row['hours']),max(1/60,float(row['hours'])*.1)),step=.25,key=f"limit_{row['id']}_{row['hours']}")
        try:
            choices=automatic_choices(appliances,protected,limits)
            result=savings_options(units,settings,appliances,target,days,protected,limits)
            with suggestions:
                render_savings_options(data,records,settings,units,target,result,choices,estimate.get('inference_sha256'))
        except ValueError as error:st.warning(str(error))
    if st.session_state.pop('budget_saved',False):st.success('Your chosen routine is saved and is now reflected in the next-bill estimate. Your bill history was kept.')
    st.caption('Approximate scenarios, not guaranteed bills. Only the suggested appliance reductions change, within the displayed limits. Other household use and saved tax/adjustment amounts stay unchanged. The same estimated peak-use share is applied to reductions; exact appliance timing is not known.')
    with st.expander('Advanced details'):
        st.write(f'Planning period: {days} days. Electricity before changes: {units:.1f} kWh. Peak hours in saved settings: {settings.get("peak_start") or "Not set"}–{settings.get("peak_end") or "Not set"}.')
        st.dataframe(pd.DataFrame(starting['lines']),hide_index=True)
        st.write('Estimated power is a starting assumption. Actual appliances differ; the two fan types and LED value include illustrative defaults. Adjust known ratings when adding an appliance.')
        st.markdown('[Appliance energy guide](https://dhs.maryland.gov/office-of-home-energy-programs/tips-for-saving-money/) · [Additional appliance ranges](https://www.occ.ohio.gov/factsheet/watts-driving-your-electric-bill)')
        if estimate.get('saved_plan') and st.button('Return to the history-based estimate'):
            clear_plan(data,settings);st.rerun()


def render_savings_options(data,records,settings,units,target,result,choices,inference_sha256=None):
    st.subheader('Suggested plans — what to use less')
    if result['already_met']:st.success('Your current estimate is already within your target. No reduction is needed.')
    elif not any(r['can_reduce'] and r['hours']>r['minimum_hours'] for r in choices):
        st.info('All appliances are currently kept unchanged. Open Adjust suggestions to allow a change.')
    else:
        if not result['reachable']:
            st.info(f"Even the biggest reductions below give about Rs {result['lowest_pkr']:,.0f}. The listed appliances alone cannot reach Rs {target:,.0f}; other household use and saved charges remain. You can still choose a lower-cost routine.")
        for index,plan in enumerate(result['plans']):
            with st.container(border=True):
                st.markdown(f"**{plan['name']}**")
                st.metric('Bill with these changes',f"Rs {plan['total_pkr']:,.2f}",delta=f"Rs {plan['saving_pkr']:,.2f} less",delta_color='off')
                for change in plan['changes']:
                    st.write(f"• {change['name']} ({change['quantity']}): use {time_label(change['new_hours'])} instead of {time_label(change['old_hours'])} per day, on {change['days']} days a week.")
                gap=plan['total_pkr']-target
                if gap>0:st.caption(f"About Rs {gap:,.0f} above your target. Suggested times are rounded to whole minutes.")
                if st.button('Accept and save this plan',key=f'save_budget_{index}'):
                    try:
                        updated=dict(settings,saved_usage_plan=dict(history_signature=history_signature(records),units=max(0,units-plan['units_saved']),inference_sha256=inference_sha256))
                        with plan_transaction(data):
                            save_appliances(data,plan['appliances'])
                            save_settings(data,updated)
                    except StorageError as error:recovery_screen(error)
                    except (OSError,ValueError):
                        st.error('Your plan could not be saved. The previous routine and estimate have been kept. Please try again.');return
                    st.session_state.budget_saved=True;st.rerun()
