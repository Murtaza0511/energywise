"""Explicit bill components; historical reconciliation and labelled scenarios."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite


def number(value, name, allow_negative=False):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'{name} must be a number.')
    if not result.is_finite() or (result < 0 and not allow_negative):
        raise ValueError(f'{name} must be finite' + ('.' if allow_negative else ' and nonnegative.'))
    return result


def money(value):
    try:return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
    except (InvalidOperation,ValueError,OverflowError):
        raise ValueError('The calculated amount is too large. Please review the units, prices and charges.')


PRICE_FIELDS={'off_peak_rate':'Off-peak price per unit','peak_rate':'Peak price per unit',
              'fixed_charge':'Fixed charge','phl_rate':'PHL surcharge per unit','peak_share':'Peak share'}

def editable_settings(settings):
    """Return safe form values and problems without changing the stored settings."""
    current=dict(settings or {});problems=[];invalid=[]
    for key,label in PRICE_FIELDS.items():
        try:
            value=float(number(current.get(key),label))
            if not isfinite(value) or (key=='peak_share' and value>1):raise ValueError(f'{label} is outside its allowed range.')
            current[key]=value
        except ValueError:
            current.pop(key,None);problems.append(label)
    charges=current.get('carried_charges')
    if not isinstance(charges,list):
        current['carried_charges']=[];problems.append('Named charges')
        if charges is not None:invalid.append(charges)
    else:
        valid=[]
        for row in charges:
            try:
                if not isinstance(row,dict) or not isinstance(row.get('name'),str) or not row['name'].strip():raise ValueError('Missing charge name')
                amount=float(number(row.get('amount_pkr'),row['name'],True))
                if not isfinite(amount):raise ValueError('Charge is too large')
                valid.append(dict(name=row['name'],amount_pkr=amount))
            except ValueError:
                problems.append('A named charge');invalid.append(row)
        current['carried_charges']=valid
    current['_invalid_charges']=invalid
    for key,default in [('peak_start','17:30'),('peak_end','22:30')]:
        if not isinstance(current.get(key,default),str):current[key]=default
        current.setdefault(key,default)
    return current,problems

def validate_settings(settings):
    if not isinstance(settings,dict):raise ValueError('Add your bill prices and charges in My bills before calculating the cost.')
    _,problems=editable_settings(settings)
    if problems:raise ValueError('Review missing or invalid bill settings in My bills: '+', '.join(problems)+'. Valid saved values have been kept.')


def calculate_bill(off_peak_kwh, peak_kwh, off_peak_rate, peak_rate, fixed_charge=0,
                   phl_rate=0, carried_charges=None, percentage_taxes=None):
    """Every extra amount is named. No utility tax formula is inferred.

    percentage_taxes are explicit user assumptions on base=energy_only or
    energy_plus_fixed, never rates guessed from a photographed tax amount.
    """
    off = number(off_peak_kwh, 'Off-peak units')
    peak = number(peak_kwh, 'Peak units')
    off_rate = number(off_peak_rate, 'Off-peak rate')
    peak_rate = number(peak_rate, 'Peak rate')
    fixed = number(fixed_charge, 'Fixed charge')
    phl = number(phl_rate, 'PHL rate')
    lines = [dict(name='Off-peak electricity', amount_pkr=money(off*off_rate)),
             dict(name='Peak electricity', amount_pkr=money(peak*peak_rate)),
             dict(name='Fixed charge', amount_pkr=money(fixed)),
             dict(name='PHL surcharge', amount_pkr=money((off+peak)*phl))]
    energy = number(lines[0]['amount_pkr'], 'Energy')+number(lines[1]['amount_pkr'], 'Energy')
    for item in carried_charges or []:
        name = str(item['name']).strip()
        if not name:
            raise ValueError('Each charge needs a name.')
        lines.append(dict(name=name,amount_pkr=money(number(item['amount_pkr'],name,True))))
    for tax in percentage_taxes or []:
        if tax['base'] not in ('energy_only','energy_plus_fixed'):
            raise ValueError('Choose the amount the tax percentage applies to.')
        base = energy if tax['base']=='energy_only' else energy+fixed
        lines.append(dict(name=tax['name'],amount_pkr=money(base*number(tax['percent'],'Tax percentage')/100)))
    total = money(sum(Decimal(str(item['amount_pkr'])) for item in lines))
    if total < 0:
        raise ValueError('Your entered credits exceed the calculated charges. Please review your bill settings in My bills.')
    return dict(consumption_kwh=float(off+peak),lines=lines,total_pkr=total)


def settings_from_bill(bill):
    extras = [dict(name=item['name'],amount_pkr=item['amount_pkr']) for item in bill['adjustment_rows']]
    extras += [dict(name=name.replace('_',' ').title(),amount_pkr=amount)
               for name,amount in bill['taxes_and_duties_pkr'].items()]
    return dict(off_peak_rate=bill['off_peak_rate_pkr_per_kwh'],peak_rate=bill['peak_rate_pkr_per_kwh'],
                fixed_charge=bill['fixed_charge_pkr'],phl_rate=bill['phl_rate_pkr_per_kwh'],
                carried_charges=extras,source_month=bill['billing_month'],
                peak_share=bill['peak_kwh']/bill['consumption_kwh'],
                peak_start='17:30',peak_end='22:30',peak_schedule_source='User supplied; editable, not automatically verified')


def reconcile_example(bill):
    return calculate_bill(bill['off_peak_kwh'],bill['peak_kwh'],**{
        key:value for key,value in settings_from_bill(bill).items()
        if key in ['off_peak_rate','peak_rate','fixed_charge','phl_rate','carried_charges']})
