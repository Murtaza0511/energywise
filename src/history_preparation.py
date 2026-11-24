"""User-authorized neighbour averaging for isolated missing consumption months."""
from personal_estimate import month_id,month_label,history_status

def fill_missing_months(records, deleted_months=()):
    history_status(records)
    lookup={month_id(r['month']):dict(r) for r in records}
    # Imported totals can mix an observed component with an averaged component.
    # Only our explicit whole-month formula can be refreshed from household totals.
    whole_average=lambda r:r.get('source','').startswith('User-approved interpolated average of ')
    result=[r for r in lookup.values() if not whole_average(r)]
    actual={v:r for v,r in lookup.items() if 'interpolated' not in r.get('source','').lower()}
    blocked={month_id(m) for m in deleted_months}
    if not lookup:return result
    # Only original immediate neighbours: never chain invented values across a long gap.
    for value in range(min(lookup)+1,max(lookup)):
        if value in lookup and not whole_average(lookup[value]):continue
        if value in blocked or value-1 not in actual or value+1 not in actual:continue
        before,after=actual[value-1],actual[value+1]
        units=(float(before['kwh'])+float(after['kwh']))/2
        old=lookup.get(value)
        result.append(old if old and float(old['kwh'])==units else dict(month=month_label(value),kwh=units,source=f"User-approved interpolated average of {before['month']} ({before['kwh']}) and {after['month']} ({after['kwh']}); not an observed bill reading"))
    return sorted(result,key=lambda r:r['month'])
