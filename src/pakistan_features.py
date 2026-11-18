"""Shared frozen-model feature transformation; no training-data dependency."""
import numpy as np

def relative_features(frame):
 scale=frame.recent_6_mean_kwh.to_numpy().clip(1)
 lags=frame[[f'lag_{i}_kwh' for i in range(1,7)]].to_numpy()/scale[:,None]
 x=np.column_stack([lags,frame.recent_3_mean_kwh/scale,(frame.lag_1_kwh-frame.lag_2_kwh)/scale,frame.target_month_sin,frame.target_month_cos,frame.target_calendar_days])
 return x,scale
