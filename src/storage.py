"""Local single-user CSV storage; no automatic loading of personal example data."""
import csv,json,os,tempfile
from pathlib import Path
from personal_estimate import month_id
from billing import number

FIELDS=['month','kwh','source']


def atomic_text(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as f:f.write(text)
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def load_records(folder):
    path=Path(folder)/'monthly_consumption.csv'
    if not path.exists():return []
    from history_preparation import fill_missing_months
    with path.open(newline='') as f:return fill_missing_months([dict(month=r['month'],kwh=float(r['kwh']),source=r['source']) for r in csv.DictReader(f)])


def save_records(folder,records):
    import io
    from history_preparation import fill_missing_months
    records=fill_missing_months(records)
    found=set();prepared=[]
    for r in records:
        month_id(r['month'])
        if r['month'] in found:raise ValueError('Duplicate month. Edit its existing record instead.')
        found.add(r['month'])
        prepared.append(dict(month=r['month'],kwh=str(number(r['kwh'],'Electricity units')),source=r.get('source','Manual entry')))
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=FIELDS);writer.writeheader();writer.writerows(sorted(prepared,key=lambda r:r['month']))
    atomic_text(Path(folder)/'monthly_consumption.csv',out.getvalue())


def load_settings(folder):
    path=Path(folder)/'settings.csv'
    if not path.exists():return None
    with path.open(newline='') as f:return {r['key']:json.loads(r['value']) for r in csv.DictReader(f)}


def save_settings(folder,settings):
    import io
    out=io.StringIO();writer=csv.writer(out);writer.writerow(['key','value'])
    for key,value in settings.items():writer.writerow([key,json.dumps(value)])
    atomic_text(Path(folder)/'settings.csv',out.getvalue())


def load_appliances(folder):
    path=Path(folder)/'appliances.csv'
    if not path.exists():return []
    with path.open(newline='') as f:
        return [dict(r,can_reduce=r['can_reduce']=='True',**{k:float(r[k]) for k in ['watts','quantity','hours','days','minimum_hours']}) for r in csv.DictReader(f)]


def save_appliances(folder,rows):
    import io
    from budget_planner import validate_appliances
    fields=['id','name','kind','watts','quantity','hours','days','minimum_hours','can_reduce']
    prepared=validate_appliances(rows)
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(prepared)
    atomic_text(Path(folder)/'appliances.csv',out.getvalue())
