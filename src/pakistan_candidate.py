"""Experimental candidate artifact; not connected to the consumer application's forecast."""
from pathlib import Path
import json,hashlib
import joblib
import pandas as pd
import numpy as np
from personal_estimate import estimate_next_month
from pakistan_features import relative_features
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/pakistan_model_comparison'

def feature_row(records):
 estimate=estimate_next_month(records);recent=sorted(records,key=lambda r:r['month'])[-6:]
 lags=[float(r['kwh']) for r in reversed(recent)];target=pd.Period(estimate['target_month'],freq='M')
 return pd.DataFrame([{**{f'lag_{i+1}_kwh':v for i,v in enumerate(lags)},'recent_3_mean_kwh':float(np.mean(lags[:3])),'recent_6_mean_kwh':float(np.mean(lags)),'target_month_sin':float(np.sin(2*np.pi*target.month/12)),'target_month_cos':float(np.cos(2*np.pi*target.month/12)),'target_calendar_days':target.days_in_month}]),str(target)

def predict_candidate(bundle,records):
 frame,target=feature_row(records);x,scale=relative_features(frame)
 value=float(np.expm1(bundle['estimator'].predict(x))[0]*scale[0])
 if not np.isfinite(value) or value<0:raise ValueError('Experimental model returned invalid consumption.')
 return dict(target_month=target,consumption_kwh=value,method=bundle['method'],status='Experimental, not validated on this household')

def save_candidate():
 from pakistan_model_comparison import build
 selection=json.loads((OUT/'selection.json').read_text());assert selection['winner']=='Relative Extra Trees'
 source=ROOT/'data/processed/pakistan/forecast_samples.csv';data=pd.read_csv(source);x,scale=relative_features(data)
 model=build('Extra Trees').fit(x,np.log1p(data.target_kwh.to_numpy()/scale))
 bundle=dict(method=selection['winner'],estimator=model,transform='relative_features_then_expm1_times_max_mean6_1',status='development_candidate_only')
 artifact=OUT/'experimental_extra_trees.joblib'
 if artifact.exists():raise ValueError('Do not overwrite candidate artifact.')
 joblib.dump(bundle,artifact)
 loaded=joblib.load(artifact);np.testing.assert_allclose(model.predict(x),loaded['estimator'].predict(x),rtol=0,atol=0)
 metadata=dict(method=selection['winner'],fitted_rows=len(data),source_households=data.household_id.nunique(),first_training_target=data.target_month.min(),last_training_target=data.target_month.max(),artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),evaluated_via_separate_grouped_rolling_folds=True,saved_fit_not_independently_scored=True,personal_household_validated=False,app_changed=False,sklearn_version=__import__('sklearn').__version__,relative_feature_names=[*[f'lag_{i}_div_scale' for i in range(1,7)],'mean3_div_scale','lag1_minus_lag2_div_scale','target_month_sin','target_month_cos','target_calendar_days'],scale='max(mean6,1 kWh)',target_transform='log1p(target_kwh/scale)')
 (OUT/'candidate_metadata.json').write_text(json.dumps(metadata,indent=2));print(json.dumps(metadata,indent=2))
if __name__=='__main__':save_candidate()
