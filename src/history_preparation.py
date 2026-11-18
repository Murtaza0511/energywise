"""User-authorized neighbour averaging for isolated missing consumption months."""
from personal_estimate import month_id,month_label,history_status

def fill_missing_months(records):
    history_status(records)
    lookup={month_id(r['month']):dict(r) for r in records}
    result=list(lookup.values())
    if not lookup:return result
    # Only original immediate neighbours: never chain invented values across a long gap.
    for value in range(min(lookup)+1,max(lookup)):
        if value in lookup or value-1 not in lookup or value+1 not in lookup:continue
        before,after=lookup[value-1],lookup[value+1]
        if any('interpolated' in r.get('source','').lower() for r in (before,after)):continue
        units=(float(before['kwh'])+float(after['kwh']))/2
        result.append(dict(month=month_label(value),kwh=units,source=f"User-approved interpolated average of {before['month']} ({before['kwh']}) and {after['month']} ({after['kwh']}); not an observed bill reading"))
    return sorted(result,key=lambda r:r['month'])
