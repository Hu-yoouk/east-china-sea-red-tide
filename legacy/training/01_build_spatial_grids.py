# -*- coding: utf-8 -*-
"""Step 4.1: Build Spatial Grid Tensor from Point Observations"""
import os, sys, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False
from scipy.interpolate import griddata
from scipy.ndimage import sobel, generic_filter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, '01_\u6570\u636e\u9884\u5904\u7406', 'cleaned_red_tide_data.csv')
OUT_DIR = os.path.join(BASE, '04_\u7a7a\u95f4CNN\u6a21\u578b', 'output_cnn')
os.makedirs(OUT_DIR, exist_ok=True)

VAR_NAMES = ['sst', 'chlorophyll', 'wind_speed', 'pressure',
             'solar_radiation', 'precipitation', 'salinity',
             'nitrate', 'phosphate', 'silicate']
N_VARS = len(VAR_NAMES)
LONS = np.array([round(120.5 + i * 0.25, 2) for i in range(13)])
LATS = np.array([round(29.0 + i * 0.25, 2) for i in range(15)])
LON_GRID, LAT_GRID = np.meshgrid(LONS, LATS)
H, W = 15, 13
T = 240
TRAIN_YEARS = list(range(2004, 2018))
VAL_YEARS = list(range(2018, 2020))
TEST_YEARS = list(range(2020, 2024))

print('[1/6] Loading point data from CSV...')
df = pd.read_csv(CSV_PATH)
df = df[(df['year'] >= 2004) & (df['year'] <= 2023)]
df['time_key'] = df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2)
unique_times = sorted(df['time_key'].unique())

spatial_tensor = np.full((T, N_VARS, H, W), np.nan, dtype=np.float32)
labels = np.full((T,), -1, dtype=np.float32)
time_keys = []

for t_idx, time_key in enumerate(unique_times):
    df_t = df[df['time_key'] == time_key]
    time_keys.append(time_key)
    label_vals = df_t['red_tide_label'].dropna().unique()
    if len(label_vals) > 0:
        labels[t_idx] = label_vals[0]
    for v_idx, var in enumerate(VAR_NAMES):
        sub = df_t[['longitude', 'latitude', var]].dropna(subset=[var])
        if len(sub) == 0:
            continue
        pts = sub[['longitude', 'latitude']].values.astype(np.float32)
        vals = sub[var].values.astype(np.float32)
        grid_vals = griddata(pts, vals, (LON_GRID, LAT_GRID), method='nearest')
        spatial_tensor[t_idx, v_idx] = grid_vals

for v_idx in range(N_VARS):
    mask = np.isnan(spatial_tensor[:, v_idx])
    if mask.any():
        valid_data = spatial_tensor[:, v_idx][~np.isnan(spatial_tensor[:, v_idx])]
        gmean = np.float32(np.mean(valid_data)) if len(valid_data) > 0 else 0.0
        spatial_tensor[:, v_idx][np.isnan(spatial_tensor[:, v_idx])] = gmean

train_mask = np.array([any(str(yr) in tk for yr in TRAIN_YEARS) for tk in time_keys])
test_mask = np.array([any(str(yr) in tk for yr in TEST_YEARS) for tk in time_keys])
val_mask = ~train_mask & ~test_mask

print('[2/6] Z-score normalization...')
var_mean = np.zeros(N_VARS, dtype=np.float32)
var_std = np.zeros(N_VARS, dtype=np.float32)
for v_idx in range(N_VARS):
    train_data = spatial_tensor[train_mask, v_idx]
    v_mean = np.float32(np.nanmean(train_data))
    v_std = np.float32(np.nanstd(train_data)) + 1e-8
    var_mean[v_idx] = v_mean
    var_std[v_idx] = v_std
    spatial_tensor[:, v_idx] = (spatial_tensor[:, v_idx] - v_mean) / v_std

print('[3/6] Computing spatial texture features...')
texture_records = []
for t_idx in range(T):
    row = {'time_key': time_keys[t_idx]}
    parts = time_keys[t_idx].split('-')
    row['year'] = int(parts[0])
    row['month'] = int(parts[1])
    row['label'] = int(labels[t_idx])
    for v_idx, var in enumerate(VAR_NAMES):
        field = spatial_tensor[t_idx, v_idx]
        sx = sobel(field, axis=0)
        sy = sobel(field, axis=1)
        grad_mag = np.sqrt(sx**2 + sy**2)
        row[var + '_grad_mean'] = np.float32(np.mean(grad_mag))
        row[var + '_grad_std'] = np.float32(np.std(grad_mag))
        local_std = generic_filter(field, lambda x: np.std(x), size=3)
        row[var + '_localstd_mean'] = np.float32(np.mean(local_std))
        row[var + '_range'] = np.float32(np.max(field) - np.min(field))
    texture_records.append(row)

pd.DataFrame(texture_records).to_csv(
    os.path.join(OUT_DIR, 'spatial_texture_features.csv'), index=False, encoding='utf-8')

print('[4/6] Saving spatial tensor...')
np.savez_compressed(os.path.join(OUT_DIR, 'spatial_tensor.npz'),
    tensor=spatial_tensor, labels=labels,
    time_keys=np.array(time_keys, dtype=object),
    var_names=np.array(VAR_NAMES, dtype=object),
    lons=LONS, lats=LATS,
    train_mask=train_mask, val_mask=val_mask, test_mask=test_mask,
    var_mean=var_mean, var_std=var_std)

print('[5/6] Generating spatial grid comparison...')
rt_idx = np.where((labels == 1) & test_mask)[0]
nr_idx = np.where((labels == 0) & test_mask)[0]
rt_t = rt_idx[0] if len(rt_idx) > 0 else 0
nr_t = nr_idx[0] if len(nr_idx) > 0 else (T // 2)

fig, axes = plt.subplots(2, N_VARS, figsize=(4 * N_VARS, 8))
fig.suptitle('Red Tide Month (top) vs Non-Red Tide Month (bottom)', fontsize=14, fontweight='bold', y=1.01)
for row_idx, (t_idx, pf) in enumerate([(rt_t, 'RT'), (nr_t, 'Non-RT')]):
    for v_idx in range(N_VARS):
        ax = axes[row_idx, v_idx]
        field = spatial_tensor[t_idx, v_idx]
        im = ax.pcolormesh(LONS, LATS, field, shading='auto', cmap='RdBu_r')
        ax.set_title(VAR_NAMES[v_idx] + ' (' + pf + ')', fontsize=8)
        if row_idx == 1: ax.set_xlabel('Lon')
        if v_idx == 0: ax.set_ylabel('Lat')
        plt.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, '01_spatial_grid_comparison.png'), dpi=150, bbox_inches='tight')
plt.close()

print('[6/6] Generating texture visualization...')
tex_vars = ['sst', 'chlorophyll', 'wind_speed', 'salinity']
fig, axes = plt.subplots(3, len(tex_vars), figsize=(16, 10))
fig.suptitle('Spatial Texture Features (RT month)', fontsize=14, fontweight='bold', y=1.01)
for vi, var in enumerate(tex_vars):
    field = spatial_tensor[rt_t, VAR_NAMES.index(var)]
    im0 = axes[0, vi].pcolormesh(LONS, LATS, field, shading='auto', cmap='RdBu_r')
    axes[0, vi].set_title(var + ' (Field)', fontsize=10)
    plt.colorbar(im0, ax=axes[0, vi], shrink=0.7)
    sx, sy = sobel(field, axis=0), sobel(field, axis=1)
    grad = np.sqrt(sx**2 + sy**2)
    im1 = axes[1, vi].pcolormesh(LONS, LATS, grad, shading='auto', cmap='hot')
    axes[1, vi].set_title(var + ' (Gradient)', fontsize=10)
    plt.colorbar(im1, ax=axes[1, vi], shrink=0.7)
    lstd = generic_filter(field, lambda x: np.std(x), size=3)
    im2 = axes[2, vi].pcolormesh(LONS, LATS, lstd, shading='auto', cmap='viridis')
    axes[2, vi].set_title(var + ' (Local Std)', fontsize=10)
    plt.colorbar(im2, ax=axes[2, vi], shrink=0.7)
    for ri in range(3):
        if ri == 2: axes[ri, vi].set_xlabel('Lon')
        if vi == 0: axes[ri, vi].set_ylabel('Lat')
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, '02_spatial_texture_features.png'), dpi=150, bbox_inches='tight')
plt.close()
print('Done. Output in:', OUT_DIR)
