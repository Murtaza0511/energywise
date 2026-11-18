"""Bulk upload, session-only photo review, and simple monthly records."""
import hashlib,json
from pathlib import Path
import pandas as pd
import streamlit as st
import bill_photo
from storage import save_records,save_settings
from billing import settings_from_bill,reconcile_example
from personal_estimate import history_status,month_id,month_label


def progress_panel(records):
    status=history_status(records);count=status['consecutive']
    st.progress(min(count/6,1.),text=f'{min(count,6)} of 6 consecutive months added · 12 months recommended')
    if status['ready']:st.success(f"Ready for an estimate · {status['total']} months recorded.")
    elif records:st.info(f"{6-min(count,6)} more months needed to complete your latest six-month history.")
    else:st.info('Upload your bills to get started. You can add them a few at a time.')
    if records:
        ids=[month_id(r['month']) for r in records]
        missing=[month_label(i) for i in range(min(ids),max(ids)+1) if i not in ids]
        needed=status['missing']
        if needed:st.warning('Needed for your first estimate: '+', '.join(needed))
        older=[m for m in missing if m not in needed]
        if older:st.caption('Other gaps in your recorded history: '+', '.join(older))


def render_bills(root,data,records):
    st.subheader('My bills')
    st.write('Upload bills → Review anything unclear → See your estimate')
    st.caption('Read on this computer. Photos are available for review during this session and are not saved as files. Currently reads month and units; prices and taxes still need manual entry.')
    photos=st.file_uploader('Choose one or several bill photos',type=['jpg','jpeg','png'],accept_multiple_files=True,key='bill_uploads') or []
    # A singleton is tolerated for test doubles and older uploader adapters.
    if not isinstance(photos,(list,tuple)):photos=[photos]
    batch=st.session_state.setdefault('bill_imports',{})
    active={}
    bar=st.progress(0.,text='Preparing your uploads…') if photos else None
    for index,photo in enumerate(photos):
        content=photo.getvalue();digest=hashlib.sha256(content).hexdigest();active[digest]=content
        if digest not in batch:
            name=Path(getattr(photo,'name',f'Bill photo {index+1}')).name
            bar.progress(index/len(photos),text=f'Reading bill {index+1} of {len(photos)} · {name}')
            try:
                result=bill_photo.recognize_photo(content)
                state=bill_photo.classify_reading(records,result)
                if state=='new':
                    merged,added=bill_photo.merge_photo_record(records,result)
                    save_records(data,merged);records=merged;state='added'
                batch[digest]=dict(name=name,result=result,state=state)
            except ValueError as error:
                batch[digest]=dict(name=name,result=dict(month=None,kwh=None),state='error',error=str(error))
        bar.progress((index+1)/len(photos),text=f'Checked {index+1} of {len(photos)} photos')
    if photos:bar.empty()
    if batch:
        done=sum(v['state'] in ['added','reviewed'] for v in batch.values())
        duplicates=sum(v['state']=='duplicate' for v in batch.values())
        attention=sum(v['state'] in ['incomplete','conflict','error'] for v in batch.values())
        st.caption(f'{done} added or reviewed · {duplicates} duplicates skipped · {attention} need attention (this session)')
        with st.expander('Upload results'):
            st.dataframe(pd.DataFrame([{'Photo':v['name'],'Bill month':v['result'].get('month') or 'Needs review','Units':v['result'].get('kwh'),'Result':v['state']} for v in batch.values()]),hide_index=True)
    from history_help_ui import missing_household_reading
    from storage import load_settings
    if not missing_household_reading(records,data,load_settings(data)):progress_panel(records)
    needs=[(key,v) for key,v in batch.items() if v['state'] in ['incomplete','conflict','error']]
    if needs:
        st.subheader('Needs attention')
        for digest,item in needs:
            result=item['result']
            with st.expander(f"{item['name']} — {item['state']}",expanded=True):
                left,right=st.columns(2)
                if digest in active:left.image(active[digest],caption='Your uploaded photo',width='stretch')
                else:left.caption('Select this photo again to see it beside the values.')
                existing=next((r for r in records if r['month']==result.get('month')),None)
                if item['state']=='conflict' and existing:right.warning(f"{result['month']} already exists: saved {existing['kwh']:g} units; this photo reads {result['kwh']:g}. Your saved value has been kept.")
                elif item['state']=='error':right.warning(item['error'])
                else:right.warning('Some values could not be read clearly. Complete or correct them below.')
                with right.form(f'review_{digest}'):
                    month=st.text_input('Bill month (YYYY-MM)',value=result.get('month') or '')
                    units=st.number_input('Electricity units shown on the bill',min_value=0.,value=result.get('kwh'))
                    replace=st.checkbox('Replace the saved record if this month already exists',value=False)
                    if st.form_submit_button('Save reviewed bill'):
                        try:
                            month_id(month)
                            old=next((r for r in records if r['month']==month),None)
                            if old and not replace:raise ValueError('This month already exists. Tick the replace option only if you want to use these values.')
                            save_records(data,[r for r in records if r['month']!=month]+[dict(month=month,kwh=units,source='Photo reading reviewed and corrected')])
                            item['state']='reviewed';st.rerun()
                        except ValueError as error:st.error(str(error))
                if right.button('Keep my saved record / dismiss',key=f'dismiss_{digest}'):
                    item['state']='dismissed';st.rerun()
    with st.expander('Add a bill without a photo'):
        with st.form('manual_bill'):
            month=st.text_input('Bill month (YYYY-MM)',placeholder='2026-10')
            units=st.number_input('Electricity units',min_value=0.,value=None)
            if st.form_submit_button('Add bill'):
                try:
                    save_records(data,[*records,dict(month=month,kwh=units,source='Manual entry')]);st.rerun()
                except ValueError as error:st.error(str(error))
    st.subheader('Your monthly bills')
    if not records:st.caption('Your bills will appear here after upload or manual entry.')
    for start in range(0,len(records),3):
        ordered=sorted(records,key=lambda r:r['month'],reverse=True)
        for column,row in zip(st.columns(3),ordered[start:start+3]):
            with column.container(border=True):
                st.markdown(f"**{row['month']}**")
                st.write(f"{row['kwh']:,.1f} electricity units")
                st.caption('Your household electricity use' if row['source'].startswith('Combined') else row['source'])
                with st.expander('Edit bill'):
                    with st.form(f'edit_bill_{row["month"]}'):
                        new_month=st.text_input('Bill month',value=row['month'])
                        new_units=st.number_input('Units',min_value=0.,value=float(row['kwh']))
                        if st.form_submit_button('Save changes'):
                            try:
                                save_records(data,[r for r in records if r['month']!=row['month']]+[dict(month=new_month,kwh=new_units,source='User-reviewed bill record')]);st.rerun()
                            except ValueError as error:st.error(str(error))
                    if st.checkbox('Remove this month',key=f'remove_check_{row["month"]}'):
                        if st.button('Remove bill record',key=f'remove_bill_{row["month"]}'):
                            save_records(data,[r for r in records if r['month']!=row['month']]);st.rerun()
    if records:
        if st.button('See my next bill estimate',type='primary',on_click=lambda:st.session_state.update(page='Next bill estimate')):pass
        st.download_button('Download my monthly records (CSV)',pd.DataFrame(records).to_csv(index=False),file_name='my_monthly_electricity.csv',mime='text/csv')
    if (root/'reports/user_bill_extraction.json').exists():
        with st.expander('Example data — testing only'):
            st.warning('Loading the examples replaces your saved monthly history and prices. It does not merge them with your uploaded bills.')
            st.caption('These are manually transcribed examples, not automatic chart extraction. Older chart readings need checking. September uses 546 units from its detailed bill.')
            if st.button('Load my example bill history and prices'):
                examples=json.loads((root/'reports/user_bill_extraction.json').read_text())
                save_records(data,[dict(month=r['month'],kwh=r['kwh'],source=r['source']) for r in examples['consumption_history']])
                save_settings(data,settings_from_bill(examples['bills'][-1]));st.rerun()
    return records
