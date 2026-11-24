"""Fixed-model personal backtest: no fitting, no settings writes, same months for baselines."""
from pathlib import Path
import hashlib,json,math
import joblib
from personal_estimate import history_status,month_id,month_label
from pakistan_candidate import predict_candidate
ROOT=Path(__file__).resolve().parents[1]
MODEL_DIR=ROOT/'reports/pakistan_model_comparison'


def load_fixed_candidate(folder=MODEL_DIR,apply_policy=True):
    folder=Path(folder)
    try:
        meta=json.loads((folder/'candidate_metadata.json').read_text())
        artifact=folder/'experimental_extra_trees.joblib'
        digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest!=meta['artifact_sha256']:raise ValueError('The saved model has changed. Recheck its integrity before testing your bills.')
        bundle=joblib.load(artifact)
        if bundle.get('method')!='Relative Extra Trees':raise ValueError('The saved model is not the fixed candidate for this check.')
        policy_path=folder/'inference_policy.json';policy=None
        if apply_policy and policy_path.exists():
            try:
                policy=json.loads(policy_path.read_text())
                if not isinstance(policy,dict) or policy.get('version')!=1 or policy.get('artifact_sha256')!=digest:raise ValueError('Policy/model mismatch')
                weight=policy['previous_month_weight']
                if type(weight) not in (int,float) or not math.isfinite(weight) or not 0<=weight<=1:raise ValueError('Invalid blend weight')
                if weight!=.25:raise ValueError('This policy version supports only the evaluated 75/25 blend')
                if not isinstance(policy.get('method'),str) or not policy['method']:raise ValueError('Invalid method name')
            except (KeyError,TypeError,ValueError):raise ValueError('The saved forecasting configuration needs review. Your original model has been kept.')
            bundle=dict(bundle,previous_month_weight=float(weight),method=policy['method'])
        meta=dict(meta,inference_policy=policy,inference_sha256=hashlib.sha256(json.dumps(dict(artifact=digest,policy=policy),sort_keys=True).encode()).hexdigest())
        return bundle,meta
    except FileNotFoundError as exc:raise ValueError('The experimental model files are missing. Your normal bill estimate still works.') from exc


def check_history(records,bundle,training_cutoff):
    history_status(records)  # Validates every value and duplicate month, not just latest six.
    ordered=sorted(records,key=lambda r:r['month']);lookup={month_id(r['month']):r for r in ordered if 'interpolated' not in r.get('source','').lower()}
    predictions=[];skipped=[]
    blended=bool(bundle.get('previous_month_weight',0))
    methods=([bundle['method'],'Original Extra Trees','Three-month average','Previous month'] if blended else ['Extra Trees (experimental)','Three-month average','Previous month'])
    for target in ordered:
        if 'interpolated' in target.get('source','').lower():
            skipped.append(dict(month=target['month'],reason='Averaged reading is not an actual bill for accuracy checking',missing_months=''));continue
        value=month_id(target['month']);needed=list(range(value-6,value))
        missing=[month_label(v) for v in needed if v not in lookup]
        if missing:
            skipped.append(dict(month=target['month'],reason='Needs six previous consecutive months',missing_months=', '.join(missing)));continue
        if month_id(target['month'])<=month_id(training_cutoff):
            skipped.append(dict(month=target['month'],reason='Not later than the fixed model training cutoff',missing_months=''));continue
        past=[lookup[v] for v in needed]
        outcome=predict_candidate(bundle,past)
        if outcome['target_month']!=target['month']:raise ValueError('Forecast month does not match the bill being checked.')
        values=[outcome['consumption_kwh'],sum(float(r['kwh']) for r in past[-3:])/3,float(past[-1]['kwh'])]
        if blended:values.insert(1,outcome['raw_model_kwh'])
        if any(not math.isfinite(v) or v<0 for v in values):raise ValueError('An invalid prediction prevents a fair comparison. No month was silently dropped.')
        for name,predicted in zip(methods,values):
            error=predicted-float(target['kwh'])
            predictions.append(dict(month=target['month'],method=name,actual_units=float(target['kwh']),predicted_units=float(predicted),error_units=error,absolute_error_units=abs(error),history_start=past[0]['month'],history_end=past[-1]['month']))
    summary=[]
    for method in methods:
        rows=[r for r in predictions if r['method']==method]
        if not rows:continue
        summary.append(dict(method=method,months_checked=len(rows),average_error_units=math.fsum(r['absolute_error_units'] for r in rows)/len(rows),rmse_units=math.sqrt(math.fsum(r['error_units']**2 for r in rows)/len(rows)),largest_error_units=max(r['absolute_error_units'] for r in rows)))
    return dict(summary=summary,predictions=predictions,skipped=skipped,months_checked=len(predictions)//len(methods),training_cutoff=training_cutoff,notice='Retrospective development comparison. These household bills have been used during model development; results are not an independent future test. Bills may cover unequal meter-reading periods. Saved appliance scenarios are not applied to historical actuals.')
