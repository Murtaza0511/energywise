"""Transparent starting estimate; not the historical French Ridge model."""
import calendar
import re
from datetime import date
from billing import number


def month_id(value):
    try:
        if not re.fullmatch(r'\d{4}-\d{2}',str(value)):
            raise ValueError('Invalid month format')
        year, month = map(int,str(value).split('-'))
        date(year,month,1)
        return year*12+month-1
    except (ValueError,TypeError):
        raise ValueError('Use a valid month in YYYY-MM format, for example 2026-10.')


MIN_MONTHS=6

def month_label(value):
    year,month=divmod(value,12)
    return f'{year:04d}-{month+1:02d}'


def history_status(records):
    ids=[month_id(r['month']) for r in records]
    if len(ids)!=len(set(ids)):
        raise ValueError('There is more than one record for a month. Please remove duplicates.')
    for r in records:number(r['kwh'],'Electricity units')
    if not ids:return dict(total=0,consecutive=0,ready=False,missing=[],target_month=None)
    present=set(ids);latest=max(ids);count=0
    while latest-count in present:count+=1
    missing=[month_label(i) for i in range(latest-5,latest+1) if i not in present]
    return dict(total=len(ids),consecutive=count,ready=count>=MIN_MONTHS,missing=missing,target_month=month_label(latest+1))


def estimate_next_month(records):
    status=history_status(records)
    if not status['ready']:
        raise ValueError('Add at least six consecutive monthly records, ending with your latest bill, to get an estimate.')
    ordered=sorted(records,key=lambda r:month_id(r['month']))
    latest=ordered[-3:]
    values=[float(number(r['kwh'],'Electricity units')) for r in latest]
    return dict(method='Average of latest three recorded months; six consecutive months required',
                source_months=[r['month'] for r in latest],target_month=status['target_month'],
                consumption_kwh=sum(values)/3,
                notice='Starting statistical estimate, not validated personal ML. Billing periods may have different lengths; prices and adjustments may change.')
