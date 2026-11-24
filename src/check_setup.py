"""Read-only local startup checks; standard library entry point."""
from pathlib import Path
import importlib,importlib.metadata,sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]

def check():
    checks=[dict(item='Python 3.12 or newer',ok=sys.version_info>=(3,12),detail=sys.version.split()[0])]
    for name,module in [('numpy','numpy'),('pandas','pandas'),('scikit-learn','sklearn'),('streamlit','streamlit'),('plotly','plotly'),('rapidocr','rapidocr'),('onnxruntime','onnxruntime'),('Pillow','PIL'),('joblib','joblib')]:
        try:
            importlib.import_module(module);version=importlib.metadata.version(name)
            checks.append(dict(item=name,ok=True,detail=version))
        except Exception as e:checks.append(dict(item=name,ok=False,detail=f'{type(e).__name__}: {e}'))
    folder=ROOT/'reports/pakistan_model_comparison'
    try:
        meta=json.loads((folder/'candidate_metadata.json').read_text());digest=hashlib.sha256((folder/'experimental_extra_trees.joblib').read_bytes()).hexdigest()
        checks.append(dict(item='Forecast model integrity',ok=digest==meta['artifact_sha256'],detail='Saved artifact hash checked'))
        actual=importlib.metadata.version('scikit-learn');checks.append(dict(item='Model scikit-learn version',ok=actual==meta['sklearn_version'],detail=f"Installed {actual}; model expects {meta['sklearn_version']}"))
        from household_model_check import load_fixed_candidate
        active,_=load_fixed_candidate();checks.append(dict(item='Forecast method configuration',ok=True,detail=active['method']))
    except Exception as e:checks.append(dict(item='Forecast model',ok=False,detail=str(e)))
    model_dir=ROOT/'models/ocr'
    if not model_dir.exists():
        try:model_dir=Path(importlib.import_module('rapidocr').__file__).parent/'models'
        except ImportError:pass
    present=list(model_dir.glob('*.onnx'));checks.append(dict(item='Local photo-reader models',ok=len(present)>=3,detail=f'{len(present)} ONNX files available; no download attempted'))
    return dict(passed=all(r['ok'] for r in checks),checks=checks)
if __name__=='__main__':
    result=check()
    for row in result['checks']:print(('OK   ' if row['ok'] else 'CHECK')+' '+row['item']+': '+row['detail'])
    print('Ready to start.' if result['passed'] else 'Setup needs attention. Follow START_HERE.md or the project setup instructions.')
    sys.exit(0 if result['passed'] else 1)
