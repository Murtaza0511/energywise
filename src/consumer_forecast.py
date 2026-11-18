"""Consumer forecast selection; frozen ML candidate with explicit failure handling."""
from personal_estimate import estimate_next_month,history_status

def forecast(records,settings=None):
    if (settings or {}).get('forecast_method')!='extra_trees':
        return estimate_next_month(records)
    status=history_status(records)
    if not status['ready']:
        raise ValueError('Add six consecutive monthly totals ending with your latest bill. Missing months are not guessed.')
    from household_model_check import load_fixed_candidate
    from pakistan_candidate import predict_candidate
    bundle,meta=load_fixed_candidate()
    result=predict_candidate(bundle,records)
    result.update(source_months=[r['month'] for r in sorted(records,key=lambda r:r['month'])[-6:]],
        notice='Experimental Pakistani Extra Trees model. On 12 combined-household historical months, average error was about 186 units versus 205 for the previous-month method. This small retrospective check does not guarantee future accuracy.',model_sha256=meta['artifact_sha256'])
    result['averaged_input_months']=[r['month'] for r in sorted(records,key=lambda r:r['month'])[-6:] if 'interpolated' in r.get('source','').lower()]
    if result['averaged_input_months']:result['notice']+=' Includes a user-approved averaged reading for '+', '.join(result['averaged_input_months'])+'.'
    return result

def combined_prices_pending(settings):
    return (settings or {}).get('billing_scope')=='combined_accounts_unconfigured'
