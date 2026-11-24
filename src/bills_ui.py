"""Bulk upload, session-only photo review, and simple monthly records."""
import hashlib,json
from math import isfinite
from pathlib import Path
import pandas as pd
import streamlit as st
import bill_photo
from storage import save_records,save_settings,delete_record,load_records
from billing import settings_from_bill,reconcile_example,number
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
    st.caption('Photos are processed by the app server for this session and are not saved as files. Currently reads month and units; prices and taxes still need manual entry. Different bills for one month can be combined after your confirmation.')
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
                state='duplicate' if bill_photo.photo_seen(records,digest) else bill_photo.classify_reading(records,result)
                if state=='new':
                    merged=bill_photo.photo_record(records,result['month'],result['kwh'],digest)
                    save_records(data,merged);records=load_records(data);state='added'
                batch[digest]=dict(name=name,result=result,state=state)
            except (ValueError,OSError) as error:
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
        for digest,item in batch.items():
            if item['state']=='duplicate' and not bill_photo.photo_seen(records,digest):
                st.caption(f"{item['name']} has the same month and units as a saved record. It was skipped to avoid double counting.")
                if st.button('This is a different bill — review it',key='review_equal_'+digest):
                    item['state']='conflict';st.rerun()
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
                    try:photo_units=float(number(result.get('kwh'),'Bill units'))
                    except (ValueError,OverflowError):photo_units=None
                    if photo_units is not None and not isfinite(photo_units):photo_units=None
                    units=st.number_input('Electricity units shown on the bill',min_value=0.,value=photo_units)
                    replace=st.checkbox('Replace the saved record if this month already exists',value=False)
                    combine=st.checkbox('This is a different bill — add its units to this month’s household total',value=False,key='combine_'+digest)
                    st.caption('Only add a separate bill whose units are not already included in the saved total. A different photo of an existing bill should be skipped.')
                    if st.form_submit_button('Save reviewed bill'):
                        try:
                            month_id(month)
                            old=next((r for r in records if r['month']==month),None)
                            if replace and combine:raise ValueError('Choose either replace or add this different bill, not both.')
                            if old and not replace and not combine:raise ValueError('This month already exists. Tick the replace option only if you want to use these values, or confirm this is a different bill to add.')
                            merged=bill_photo.photo_record(records,month,units,digest,mode='add' if combine else 'replace' if replace else 'new',confirmed=combine)
                            save_records(data,merged)
                            item['state']='reviewed';st.rerun()
                        except (ValueError,OSError) as error:st.error(str(error))
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
                photo_source=row['source'].startswith(bill_photo.PHOTO_SOURCE)
                st.caption('Your household electricity use · bill photo records' if photo_source else 'Your household electricity use' if row['source'].startswith('Combined') else row['source'])
                with st.expander('Edit bill'):
                    with st.form(f'edit_bill_{row["month"]}'):
                        new_month=st.text_input('Bill month',value=row['month'])
                        new_units=st.number_input('Units',min_value=0.,value=float(row['kwh']))
                        if st.form_submit_button('Save changes'):
                            try:
                                source=bill_photo.reviewed_photo_source(row,new_units)
                                save_records(data,[r for r in records if r['month']!=row['month']]+[dict(month=new_month,kwh=new_units,source=source)],deleted_months=[row['month']] if new_month!=row['month'] else []);st.rerun()
                            except ValueError as error:st.error(str(error))
                    if st.checkbox('Remove this month',key=f'remove_check_{row["month"]}'):
                        if st.button('Remove bill record',key=f'remove_bill_{row["month"]}'):
                            delete_record(data,records,row['month']);st.rerun()
    if records:
        if st.button('See my next bill estimate',type='primary',on_click=lambda:st.session_state.update(page='Next bill estimate')):pass
        st.download_button('Download my monthly records (CSV)',pd.DataFrame(records).to_csv(index=False),file_name='my_monthly_electricity.csv',mime='text/csv')
    principal=st.session_state.get('_identity')
    private_examples_allowed=principal is None or (isinstance(principal,dict) and principal.get('role')=='owner')
    if private_examples_allowed and (root/'reports/user_bill_extraction.json').exists():
        with st.expander('Example data — testing only'):
            st.warning('Loading the examples replaces your saved monthly history and prices. It does not merge them with your uploaded bills.')
            st.caption('These are manually transcribed examples, not automatic chart extraction. Older chart readings need checking. September uses 546 units from its detailed bill.')
            if st.button('Load my example bill history and prices'):
                examples=json.loads((root/'reports/user_bill_extraction.json').read_text())
                save_records(data,[dict(month=r['month'],kwh=r['kwh'],source=r['source']) for r in examples['consumption_history']])
                save_settings(data,settings_from_bill(examples['bills'][-1]));st.rerun()
    return records
