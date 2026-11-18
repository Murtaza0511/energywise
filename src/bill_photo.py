"""Local OCR. Unknown fields remain missing, never zero-filled."""
import re
from pathlib import Path


_engine=None

def recognize_photo(content):
    global _engine
    if len(content)>20*1024*1024:
        raise ValueError('Please upload a photo smaller than 20 MB.')
    try:
        import numpy as np
        from PIL import Image,ImageOps
        from io import BytesIO
        from rapidocr import RapidOCR
        image=ImageOps.exif_transpose(Image.open(BytesIO(content))).convert('RGB')
        if image.width*image.height>30_000_000:
            raise ValueError('Please upload a smaller photo (under 30 megapixels).')
        if _engine is None:
            local_models=Path(__file__).resolve().parents[1]/'models/ocr'
            _engine=RapidOCR(params={'Global.model_root_dir':str(local_models)}) if local_models.is_dir() else RapidOCR()
        results=[]
        for angle in (0,90,270,180):
            view=image.rotate(angle,expand=True) if angle else image
            output=_engine(np.array(view))
            observations=[]
            if output.txts is not None:
                for text,box,score in zip(output.txts,output.boxes,output.scores):
                    xs=box[:,0];ys=box[:,1]
                    observations.append(dict(text=text,confidence=float(score),x=float(min(xs)/view.width),y=float(1-max(ys)/view.height),width=float((max(xs)-min(xs))/view.width),height=float((max(ys)-min(ys))/view.height)))
            result=parse_observations(observations)
            results.append(result)
            if result['month'] is not None and result['kwh'] is not None:return result
        # Retain a partial result only when the attempted orientations agree.
        values={key:{r[key] for r in results if r[key] is not None} for key in ('month','kwh')}
        return reading_result(*(next(iter(values[k])) if len(values[k])==1 else None for k in ('month','kwh')))
    except ValueError:raise
    except Exception as exc:
        raise ValueError('The photo reader could not finish. Try a clearer JPG or PNG, or enter the bill manually.') from exc


MONTHS={name:i+1 for i,name in enumerate(('jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'))}
MONTH_VALUE=r'([A-Za-z]{3})[- /](\d{2,4})'
BILL_LABEL=r'b[i1l]{1,4}\s*month'

def reading_result(month,kwh):
    warnings=[]
    if month is None:warnings.append('Bill month could not be read unambiguously. Enter it below.')
    if kwh is None:warnings.append('Current-month units could not be read unambiguously. Enter them below.')
    return dict(month=month,kwh=kwh,warnings=warnings)

def parse_observations(observations):
    # Vertical OCR boxes from a sideways bill must not be treated as upright layout.
    rows=[r for r in observations if r.get('confidence',1)>=.8 and r['width']>=r['height']*1.2]
    found=set();units=set()
    def add_month(match):
        mon,year=match
        if mon.lower() in MONTHS:
            y=int(year);y=y+2000 if y<100 else y
            found.add(f'{y:04d}-{MONTHS[mon.lower()]:02d}')
    def below(label,candidate,distance=.065):
        return 0<=label['y']-candidate['y']<=distance and abs((label['x']+label['width']/2)-(candidate['x']+candidate['width']/2))<max(.06,label['width']/2)
    for r in rows:
        for match in re.findall(BILL_LABEL+r'\s*[:;]?\s*'+MONTH_VALUE,r['text'],re.I):add_month(match)
        if re.fullmatch(BILL_LABEL+r'\s*[:;]?',r['text'].strip(),re.I):
            for candidate in rows:
                match=re.fullmatch(MONTH_VALUE,candidate['text'].strip(),re.I)
                if match and below(r,candidate):add_month(match.groups())
        units.update(float(v.replace(',','')) for v in re.findall(r'\b([\d,]+(?:\.\d+)?)\s*Units\s*=',r['text'],re.I))
    current=[r for r in rows if re.match(r'^Current\s+Month\b',r['text'].strip(),re.I)]
    for label in current:
        for candidate in rows:
            match=re.fullmatch(r'([\d,]+(?:\.\d+)?)\s*Units\s*=?',candidate['text'].strip(),re.I)
            if match and below(label,candidate,.08):units.add(float(match[1].replace(',','')))
    # Older K-Electric summary: month sits right of the issue date on the invoice row;
    # current units are the first left-hand Units summary below Residential.
    invoice=[r for r in rows if re.fullmatch(r'Invoice\s+Number',r['text'].strip(),re.I)]
    account=[r for r in rows if re.fullmatch(r'Account\s+Number',r['text'].strip(),re.I)]
    payable=[r for r in rows if re.fullmatch(r'Amount\s+Payable',r['text'].strip(),re.I)]
    residential=[r for r in rows if re.fullmatch('Residential',r['text'].strip(),re.I)]
    invoice_numbers=[r for r in rows if re.fullmatch(r'\d{12}',r['text'].strip())]
    account_numbers=[r for r in rows if re.fullmatch(r'0\d{12}',r['text'].strip())]
    residential_tariff=any(re.fullmatch(r'A1[- ]R',r['text'].strip(),re.I) for r in rows)
    if invoice_numbers and account_numbers and residential and residential_tariff:
        invoice=invoice or invoice_numbers
        for label in invoice:
            dates=[r for r in rows if re.fullmatch(r'\d{1,2}[- /][A-Za-z]{3}[- /]\d{2,4}',r['text'].strip()) and r['x']>label['x'] and -.02<=label['y']-r['y']<.07]
            for date in dates:
                for candidate in rows:
                    match=re.fullmatch(MONTH_VALUE,candidate['text'].strip(),re.I)
                    if match and candidate['x']>date['x']+date['width'] and abs(candidate['y']-date['y'])<max(.012,date['height']):add_month(match.groups())
        candidates=[]
        for label in residential:
            for candidate in rows:
                match=re.fullmatch(r'([\d,]+)\s*Units',candidate['text'].strip(),re.I)
                if match and below(label,candidate,.1):candidates.append((candidate['y'],float(match[1].replace(',',''))))
        if candidates:
            top=max(y for y,v in candidates)
            units.update(v for y,v in candidates if abs(y-top)<.008)
    month=next(iter(found)) if len(found)==1 else None
    kwh=next(iter(units)) if len(units)==1 else None
    return reading_result(month,kwh)


def merge_photo_record(records,result):
    if result['month'] is None or result['kwh'] is None:
        return records,False
    # Do not silently overwrite an existing month with a new OCR reading.
    if any(r['month']==result['month'] for r in records):return records,False
    return [*records,dict(month=result['month'],kwh=result['kwh'],source='Photo reading — editable; check against bill')],True


def classify_reading(records,result):
    """Return an import decision; malformed/ambiguous fields never overwrite history."""
    from personal_estimate import month_id
    from billing import number
    if result.get('month') is None or result.get('kwh') is None:return 'incomplete'
    try:month_id(result['month']);number(result['kwh'],'Electricity units')
    except ValueError:return 'incomplete'
    existing=next((r for r in records if r['month']==result['month']),None)
    if existing is None:return 'new'
    return 'duplicate' if float(existing['kwh'])==float(result['kwh']) else 'conflict'
