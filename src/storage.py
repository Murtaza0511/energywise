"""Local single-user CSV storage; no automatic loading of personal example data."""
import csv,json,os,tempfile,hashlib,uuid
from pathlib import Path
from personal_estimate import month_id
from billing import number

FIELDS=['month','kwh','source']
DELETED='User-deleted month; do not average automatically'

class StorageError(ValueError):
    def __init__(self,path):
        self.path=Path(path)
        super().__init__(f'We could not read {self.path.name}. Your saved file has been kept unchanged.')

def read_csv(path,required):
    try:
        with Path(path).open(newline='',encoding='utf-8') as f:
            reader=csv.DictReader(f)
            if not reader.fieldnames or not set(required)<=set(reader.fieldnames):raise ValueError('Missing columns')
            rows=list(reader)
            if any(None in row or any(row.get(k) is None for k in required) for row in rows):raise ValueError('Incomplete row')
            return rows
    except (OSError,UnicodeError,csv.Error,ValueError) as exc:raise StorageError(path) from exc

def read_history(path):
    try:
        rows=read_csv(path,FIELDS)
        for row in rows:
            month_id(row['month']);row['kwh']=float(number(row['kwh'],'Electricity units'))
        from personal_estimate import history_status
        history_status(rows)
        return rows
    except (ValueError,TypeError,KeyError,OverflowError) as exc:raise StorageError(path) from exc

def verify_file(path):
    """Check a candidate before it can become a recovery backup."""
    name=Path(path).name
    if name=='monthly_consumption.csv':read_history(path)
    elif name=='settings.csv':
        rows=read_csv(path,['key','value']);keys=[r['key'] for r in rows]
        if len(keys)!=len(set(keys)):raise ValueError('Duplicate settings')
        settings={r['key']:json.loads(r['value']) for r in rows}
        from billing import validate_settings
        validate_settings(settings)
    elif name=='appliances.csv':load_appliances(Path(path).parent)
    else:raise ValueError('Unsupported recovery file')

def remember_backup(path):
    path=Path(path)
    if not path.exists():return
    try:verify_file(path)
    except (ValueError,KeyError,TypeError,OSError):return
    content=path.read_bytes();backup=path.parent/'.backups'/path.name
    atomic_text(backup,content.decode('utf-8'))
    atomic_text(backup.with_suffix('.sha256'),hashlib.sha256(content).hexdigest())

def verified_backup(path):
    path=Path(path);backup=path.parent/'.backups'/path.name
    try:
        if hashlib.sha256(backup.read_bytes()).hexdigest()!=backup.with_suffix('.sha256').read_text():return None
        verify_file(backup)
        return backup
    except (ValueError,KeyError,TypeError,OSError):return None

def restore_backup(path):
    path=Path(path);backup=verified_backup(path)
    if backup is None:raise ValueError('No verified backup is available. Your existing file has been kept.')
    if path.exists():
        preserved=path.parent/'.backups'/('unreadable-'+uuid.uuid4().hex+'-'+path.name)
        atomic_text(preserved,path.read_bytes())
    atomic_text(path,backup.read_bytes())

def write_with_backup(path,text):
    remember_backup(path)
    atomic_text(path,text)
    # On first valid save, establish a recovery copy. Never overwrite a prior backup here.
    if not (Path(path).parent/'.backups'/Path(path).name).exists():remember_backup(path)


def atomic_text(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        if isinstance(text,bytes):
            with os.fdopen(fd,'wb') as f:f.write(text)
        else:
            with os.fdopen(fd,'w',encoding='utf-8',newline='') as f:f.write(text)
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def load_records(folder):
    path=Path(folder)/'monthly_consumption.csv'
    if not path.exists():return []
    from history_preparation import fill_missing_months
    rows=read_history(path)
    return fill_missing_months([r for r in rows if r['source']!=DELETED], [r['month'] for r in rows if r['source']==DELETED])


def save_records(folder,records,deleted_months=()):
    import io
    from history_preparation import fill_missing_months
    path=Path(folder)/'monthly_consumption.csv'
    previous=read_history(path) if path.exists() else []
    deleted={r['month'] for r in previous if r['source']==DELETED}|set(deleted_months)
    for month in deleted:month_id(month)
    supplied={r['month'] for r in records if 'interpolated' not in r.get('source','').lower()}
    deleted-=supplied
    records=fill_missing_months(records,deleted)
    found=set();prepared=[]
    for r in records:
        month_id(r['month'])
        if r['month'] in found:raise ValueError('Duplicate month. Edit its existing record instead.')
        found.add(r['month'])
        prepared.append(dict(month=r['month'],kwh=str(number(r['kwh'],'Electricity units')),source=r.get('source','Manual entry')))
    prepared.extend(dict(month=m,kwh='0',source=DELETED) for m in deleted)
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=FIELDS);writer.writeheader();writer.writerows(sorted(prepared,key=lambda r:r['month']))
    write_with_backup(path,out.getvalue())

def delete_record(folder,records,month):
    month_id(month)
    save_records(folder,[r for r in records if r['month']!=month],deleted_months=[month])


def load_settings(folder):
    path=Path(folder)/'settings.csv'
    if not path.exists():return None
    try:
        rows=read_csv(path,['key','value']);keys=[r['key'] for r in rows]
        if len(keys)!=len(set(keys)):raise ValueError('Duplicate settings')
        return {r['key']:json.loads(r['value']) for r in rows}
    except (ValueError,TypeError,KeyError) as exc:raise StorageError(path) from exc


def save_settings(folder,settings):
    import io
    out=io.StringIO();writer=csv.writer(out);writer.writerow(['key','value'])
    for key,value in settings.items():writer.writerow([key,json.dumps(value)])
    write_with_backup(Path(folder)/'settings.csv',out.getvalue())


def load_appliances(folder):
    path=Path(folder)/'appliances.csv'
    if not path.exists():return []
    try:
        from budget_planner import validate_appliances
        rows=read_csv(path,['id','name','kind','watts','quantity','hours','days','minimum_hours','can_reduce'])
        if any(r['can_reduce'] not in ('True','False') for r in rows):raise ValueError('Invalid reduction permission')
        return validate_appliances([dict(r,can_reduce=r['can_reduce']=='True') for r in rows])
    except (ValueError,KeyError,TypeError) as exc:raise StorageError(path) from exc


def save_appliances(folder,rows):
    import io
    from budget_planner import validate_appliances
    fields=['id','name','kind','watts','quantity','hours','days','minimum_hours','can_reduce']
    prepared=validate_appliances(rows)
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(prepared)
    write_with_backup(Path(folder)/'appliances.csv',out.getvalue())


def recovery_screen(error):
    import streamlit as st
    st.error(str(error))
    st.write('We stopped here to protect your saved data. No records were erased or replaced with examples.')
    backup=verified_backup(error.path)
    if backup:
        st.info('A verified backup is available. Restoring it may undo your most recent edits. The unreadable file will also be preserved.')
        if st.button('Restore verified backup',key='restore_'+error.path.name):
            try:restore_backup(error.path);st.rerun()
            except (ValueError,OSError) as exc:st.error(str(exc))
    else:st.info('No verified backup is available for this file. Keep the original file and ask for help restoring a known-good copy. We will not reset your history automatically.')
    st.stop()
