"""Consumer forecast selection; frozen ML candidate with explicit failure handling."""
from personal_estimate import estimate_next_month,history_status

def validated_method(settings=None):
    method=(settings or {}).get('forecast_method')
    if method not in (None,'extra_trees','mean3','three_month_average'):
        raise ValueError('The saved forecasting method is unsupported. Choose Extra Trees or the three-month average in My bills.')
    return method

def forecast(records,settings=None):
    method=validated_method(settings)
    if method!='extra_trees':
        return estimate_next_month(records)
    status=history_status(records)
    if not status['ready']:
        raise ValueError('Add six consecutive monthly totals ending with your latest bill. Missing months are not guessed.')
    from household_model_check import load_fixed_candidate
    from pakistan_candidate import predict_candidate
    bundle,meta=load_fixed_candidate()
    result=predict_candidate(bundle,records)
    blended=bool(bundle.get('previous_month_weight',0))
    notice=('Experimental Pakistani Extra Trees/recent-bill blend. On 12 previously used household months, average error was about 165 units versus 186 for the original model and 205 for the previous-month method. These are development results, not an independent future accuracy test.' if blended else 'Experimental Pakistani Extra Trees model. On 12 household historical months, average error was about 186 units versus 205 for the previous-month method. This retrospective check does not guarantee future accuracy.')
    result.update(source_months=[r['month'] for r in sorted(records,key=lambda r:r['month'])[-6:]],
        notice=notice,model_sha256=meta['artifact_sha256'],inference_sha256=meta['inference_sha256'])
    result['averaged_input_months']=[r['month'] for r in sorted(records,key=lambda r:r['month'])[-6:] if 'interpolated' in r.get('source','').lower()]
    if result['averaged_input_months']:result['notice']+=' Includes a user-approved averaged reading for '+', '.join(result['averaged_input_months'])+'.'
    return result

def combined_prices_pending(settings):
    return (settings or {}).get('billing_scope')=='combined_accounts_unconfigured'
