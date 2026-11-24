"""Bill-anchored, constrained appliance scenarios; not a learned forecast."""
import calendar,copy,math
from billing import number,calculate_bill

PRESETS={
 'Ordinary ceiling fan':88.,
 'Energy-saving fan':30.,
 'LED light':10.,
 'AC (small / around 1 ton)':1200.,
 'Large LED television':200.,
 'Washing machine':512.,
 'Iron':1100.,
}

def validate_appliances(rows):
    checked=[];seen=set()
    for row in rows:
        r=dict(row)
        if not r.get('id') or r['id'] in seen:raise ValueError('Each appliance group needs a unique ID.')
        seen.add(r['id'])
        if r.get('kind') not in PRESETS:raise ValueError('Choose a supported appliance type.')
        if not str(r.get('name','')).strip():raise ValueError('Give the appliance a name.')
        for key in ['watts','quantity','hours','days','minimum_hours']:
            r[key]=float(number(r[key],key.replace('_',' ')))
        if r['quantity']<1 or not r['quantity'].is_integer():raise ValueError('Quantity must be a whole number of at least one.')
        if r['watts']<=0:raise ValueError('Power must be above zero.')
        if not 0<=r['hours']<=24:raise ValueError('Daily use must be from zero to 24 hours.')
        if not 1<=r['days']<=7 or not r['days'].is_integer():raise ValueError('Days per week must be a whole number from 1 to 7.')
        if r['minimum_hours']>r['hours']:raise ValueError('Shortest acceptable use cannot exceed current daily use.')
        if not isinstance(r.get('can_reduce'),bool):raise ValueError('Choose whether this appliance can be reduced.')
        checked.append(r)
    return checked


def monthly_use(row,month_days):
    return row['quantity']*row['watts']/1000*row['hours']*row['days']/7*month_days


def bill_for_units(units,settings):
    units=float(number(units,'Electricity units'))
    from billing import validate_settings
    validate_settings(settings)
    share=float(number(settings['peak_share'],'Peak share'))
    if share>1:raise ValueError('Peak share must be between zero and one.')
    return calculate_bill(units*(1-share),units*share,**{k:settings[k] for k in ['off_peak_rate','peak_rate','fixed_charge','phl_rate','carried_charges']})


def suggest_plans(base_units,settings,appliances,target,month_days):
    base=float(number(base_units,'Starting electricity use'))
    target=float(number(target,'Target bill'))
    if not 28<=month_days<=31:raise ValueError('Choose a valid monthly period.')
    rows=validate_appliances(appliances)
    starting=bill_for_units(base,settings)['total_pkr']
    total=sum(monthly_use(r,month_days) for r in rows)
    if total>base+1e-6:
        raise ValueError('Your appliance routine adds up to more electricity than the bill-based estimate. Review the quantities, hours or estimated power before making a plan.')
    capacity=[(r['hours']-r['minimum_hours'])*r['quantity']*r['watts']/1000*r['days']/7*month_days if r['can_reduce'] else 0. for r in rows]
    maximum=sum(capacity)
    minimum_bill=bill_for_units(max(0,base-maximum),settings)['total_pkr']
    needed=0.
    if target<starting:
        lo,hi=0.,maximum
        if minimum_bill>target:needed=maximum
        else:
            for _ in range(60):
                mid=(lo+hi)/2
                if bill_for_units(base-mid,settings)['total_pkr']<=target:hi=mid
                else:lo=mid
            needed=hi
    plans=[]
    for mode in ['Share changes across appliances','Change biggest electricity users first']:
        cuts=[0.]*len(rows)
        if mode.startswith('Share'):
            if maximum:cuts=[needed*c/maximum for c in capacity]
        else:
            remaining=needed
            for i in sorted(range(len(rows)),key=lambda i:capacity[i],reverse=True):
                cuts[i]=min(capacity[i],remaining);remaining=max(0,remaining-cuts[i])
        proposed=copy.deepcopy(rows);changes=[]
        for i,r in enumerate(rows):
            per_hour=r['quantity']*r['watts']/1000*r['days']/7*month_days
            hours=r['hours']-cuts[i]/per_hour
            # Round UP to a whole minute: never promise savings from undisplayed time.
            hours=max(r['minimum_hours'],min(r['hours'],math.ceil((hours-1e-10)*60)/60))
            proposed[i]['hours']=hours
            if r['hours']-hours>1e-8:
                changes.append(dict(name=r['name'],quantity=int(r['quantity']),days=int(r['days']),old_hours=r['hours'],new_hours=hours))
        saved=sum(monthly_use(a,month_days)-monthly_use(b,month_days) for a,b in zip(rows,proposed))
        amount=bill_for_units(max(0,base-saved),settings)['total_pkr']
        if not any([r['hours'] for r in previous['appliances']]==[r['hours'] for r in proposed] for previous in plans):
            plans.append(dict(name=mode,changes=changes,appliances=proposed,total_pkr=amount,saving_pkr=round(starting-amount,2),units_saved=saved))
    return dict(starting_pkr=starting,lowest_pkr=minimum_bill,already_met=target>=starting,reachable=minimum_bill<=target,plans=plans,unlisted_kwh=max(0,base-total),month_days=month_days)


def automatic_choices(appliances,protected_ids=(),minimum_hours=None):
    """Suggest first using a labelled half-use starting limit; apply user overrides after."""
    rows=validate_appliances(appliances)
    limits=minimum_hours or {}
    for row in rows:
        row['can_reduce']=row['id'] not in protected_ids
        row['minimum_hours']=float(limits.get(row['id'],row['hours']/2))
    return validate_appliances(rows)


def savings_options(base_units,settings,appliances,target,month_days,protected_ids=(),minimum_hours=None):
    """Three concrete routines, preserving a positive usage floor and user protections."""
    rows=validate_appliances(appliances)
    target=float(number(target,'Target bill'))
    starting=bill_for_units(base_units,settings)['total_pkr']
    plans=[]
    for name,reduction in [('Small savings',.25),('Medium savings',.5),('Biggest savings',.9)]:
        choices=[]
        for original in rows:
            row=dict(original)
            floor=min(row['hours'],max(1/60,row['hours']*.1))
            requested=float((minimum_hours or {}).get(row['id'],floor))
            row['can_reduce']=row['id'] not in protected_ids
            row['minimum_hours']=max(floor,requested,row['hours']*(1-reduction))
            choices.append(row)
        # Show the full tier's concrete savings, even when the requested target is unreachable.
        result=suggest_plans(base_units,settings,choices,0,month_days)
        plan=result['plans'][0]
        plan['name']=name
        plan['reaches_target']=plan['total_pkr']<=target
        plans.append(plan)
    return dict(plans=plans,already_met=target>=starting,reachable=any(p['reaches_target'] for p in plans),lowest_pkr=min(p['total_pkr'] for p in plans))
