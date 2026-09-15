const Database = require('better-sqlite3');
const fs = require('fs');
const path = require('path');

const DB_PATH = process.argv[2];
if (!DB_PATH) {
  console.error('请提供数据库路径：node scripts/export-data.cjs 数据库路径');
  process.exit(2);
}
const OUTPUT_DIR = path.resolve(__dirname, '../public/data');
const SAMPLES_PER_PAGE = 500;

console.log('Reading database...');
const db = new Database(DB_PATH, { readonly: true });

const rows = db.prepare('SELECT * FROM integrated_data ORDER BY year, month, longitude, latitude').all();
db.close();

console.log(`Loaded ${rows.length} records.`);

if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// ===== Helper functions =====

function mean(values) {
  const valid = values.filter(v => v != null);
  if (valid.length === 0) return null;
  return valid.reduce((a, b) => a + b, 0) / valid.length;
}

function stddev(values, meanVal) {
  const valid = values.filter(v => v != null);
  if (valid.length < 2) return 0;
  const m = meanVal ?? mean(valid);
  return Math.sqrt(valid.reduce((s, v) => s + (v - m) ** 2, 0) / (valid.length - 1));
}

function pearsonCorrelation(xs, ys) {
  const pairs = [];
  for (let i = 0; i < xs.length; i++) {
    if (xs[i] != null && ys[i] != null) pairs.push([xs[i], ys[i]]);
  }
  if (pairs.length < 3) return 0;
  const mx = mean(pairs.map(p => p[0]));
  const my = mean(pairs.map(p => p[1]));
  const sx = stddev(pairs.map(p => p[0]), mx);
  const sy = stddev(pairs.map(p => p[1]), my);
  if (sx === 0 || sy === 0) return 0;
  const cov = pairs.reduce((s, p) => s + (p[0] - mx) * (p[1] - my), 0) / (pairs.length - 1);
  return cov / (sx * sy);
}

// ===== 1. Summary Statistics =====
console.log('Computing summary statistics...');

const years = rows.map(r => r.year).filter(v => v != null);
const months = rows.map(r => r.month).filter(v => v != null);
const lngs = rows.map(r => r.longitude).filter(v => v != null);
const lats = rows.map(r => r.latitude).filter(v => v != null);
const redTideLabels = rows.map(r => r.red_tide_label);

const redTideCount = redTideLabels.filter(v => v === 1).length;
const totalCount = rows.length;

const monthlyStats = [];
for (let y = Math.min(...years); y <= Math.max(...years); y++) {
  for (let m = 1; m <= 12; m++) {
    const monthRows = rows.filter(r => r.year === y && r.month === m);
    if (monthRows.length === 0) continue;
    const rtCount = monthRows.filter(r => r.red_tide_label === 1).length;
    const rtAreaTotal = monthRows.reduce((s, r) => s + (r.red_tide_area || 0), 0);
    monthlyStats.push({
      year: y, month: m,
      total: monthRows.length,
      red_tide_count: rtCount,
      red_tide_rate: +(rtCount / monthRows.length).toFixed(4),
      red_tide_area_total: +(rtAreaTotal).toFixed(2),
      avg_chlorophyll: +((mean(monthRows.map(r => r.chlorophyll))) || 0).toFixed(4),
      avg_sst: +((mean(monthRows.map(r => r.sst))) || 0).toFixed(2),
      avg_salinity: +(mean(monthRows.map(r => r.salinity)) || 0).toFixed(2),
    });
  }
}

const yearlyStats = [];
for (let y = Math.min(...years); y <= Math.max(...years); y++) {
  const yearRows = rows.filter(r => r.year === y);
  const rtCount = yearRows.filter(r => r.red_tide_label === 1).length;
  yearlyStats.push({
    year: y,
    total: yearRows.length,
    red_tide_count: rtCount,
    red_tide_rate: +(rtCount / yearRows.length).toFixed(4),
  });
}

const stats = {
  total_samples: totalCount,
  red_tide_count: redTideCount,
  red_tide_rate: +(redTideCount / totalCount).toFixed(4),
  time_range: { from: `${Math.min(...years)}-${String(Math.min(...months)).padStart(2, '0')}`, to: `${Math.max(...years)}-${String(Math.max(...months)).padStart(2, '0')}` },
  spatial_extent: {
    lon_min: +Math.min(...lngs).toFixed(4), lon_max: +Math.max(...lngs).toFixed(4),
    lat_min: +Math.min(...lats).toFixed(4), lat_max: +Math.max(...lats).toFixed(4),
  },
  unique_grid_cells: new Set(rows.map(r => `${r.longitude}_${r.latitude}`)).size,
  monthly_stats: monthlyStats,
  yearly_stats: yearlyStats,
};

fs.writeFileSync(path.join(OUTPUT_DIR, 'stats.json'), JSON.stringify(stats, null, 2));
console.log('  -> stats.json');

// ===== 2. Geo Data (aggregated by grid cell) =====
console.log('Computing geo data...');

const geoMap = new Map();
for (const r of rows) {
  const key = `${r.longitude}_${r.latitude}`;
  if (!geoMap.has(key)) {
    geoMap.set(key, {
      longitude: r.longitude,
      latitude: r.latitude,
      values: [],
    });
  }
  geoMap.get(key).values.push(r);
}

const geoData = [];
for (const [, cell] of geoMap) {
  const vs = cell.values;
  const rtCount = vs.filter(v => v.red_tide_label === 1).length;
  const fields = ['sst', 'chlorophyll', 'wind_speed', 'pressure', 'solar_radiation',
    'precipitation', 'salinity', 'nitrate', 'phosphate', 'silicate'];

  const entry = {
    longitude: cell.longitude,
    latitude: cell.latitude,
    sample_count: vs.length,
    red_tide_count: rtCount,
    red_tide_frequency: +(rtCount / vs.length).toFixed(4),
    risk_score: Math.round((rtCount / vs.length) * 100),
    risk_level: rtCount / vs.length >= 0.5 ? '高风险' : rtCount / vs.length >= 0.25 ? '中风险' : '低风险',
    organisms: [...new Set(vs.map(v => v.red_tide_organism).filter(Boolean))],
    avg_red_tide_area: +((mean(vs.map(v => v.red_tide_area))) || 0).toFixed(2),
  };
  for (const f of fields) {
    const vals = vs.map(v => v[f]);
    entry[`avg_${f}`] = +(mean(vals) || 0).toFixed(4);
    entry[`${f}_has_null`] = vals.some(v => v == null);
  }
  geoData.push(entry);
}

geoData.sort((a, b) => b.sample_count - a.sample_count);

fs.writeFileSync(path.join(OUTPUT_DIR, 'geo_data.json'), JSON.stringify(geoData, null, 2));
console.log(`  -> geo_data.json (${geoData.length} grid cells)`);

// ===== 3. Time Series (monthly aggregation) =====
console.log('Computing time series...');

const timeSeriesByMonth = new Map();
for (const r of rows) {
  const ym = `${r.year}-${String(r.month).padStart(2, '0')}`;
  if (!timeSeriesByMonth.has(ym)) timeSeriesByMonth.set(ym, []);
  timeSeriesByMonth.get(ym).push(r);
}

const timeSeries = [];
for (const [ym, recs] of timeSeriesByMonth) {
  const [y, m] = ym.split('-').map(Number);
  const rtCount = recs.filter(v => v.red_tide_label === 1).length;
  const entry = {
    year: y, month: m, total: recs.length,
    red_tide_count: rtCount,
    red_tide_rate: +(rtCount / recs.length).toFixed(4),
    red_tide_area_total: +(recs.reduce((s, r) => s + (r.red_tide_area || 0), 0)).toFixed(2),
  };
  const fields = ['sst', 'chlorophyll', 'wind_speed', 'pressure', 'solar_radiation',
    'precipitation', 'salinity', 'nitrate', 'phosphate', 'silicate'];
  for (const f of fields) {
    entry[`avg_${f}`] = +(mean(recs.map(r => r[f])) || 0).toFixed(4);
  }
  timeSeries.push(entry);
}
timeSeries.sort((a, b) => a.year - b.year || a.month - b.month);

fs.writeFileSync(path.join(OUTPUT_DIR, 'time_series.json'), JSON.stringify(timeSeries, null, 2));
console.log(`  -> time_series.json (${timeSeries.length} months)`);

// ===== 4. Correlation Matrix =====
console.log('Computing correlation matrix...');

const corrFields = [
  { key: 'sst', label: '海温' },
  { key: 'chlorophyll', label: '叶绿素' },
  { key: 'wind_speed', label: '风速' },
  { key: 'pressure', label: '气压' },
  { key: 'solar_radiation', label: '太阳辐射' },
  { key: 'precipitation', label: '降水量' },
  { key: 'salinity', label: '盐度' },
  { key: 'nitrate', label: '硝酸盐' },
  { key: 'phosphate', label: '磷酸盐' },
  { key: 'silicate', label: '硅酸盐' },
  { key: 'red_tide_area', label: '赤潮面积' },
];

const labels = corrFields.map(f => f.label);
const n = corrFields.length;
const matrix = Array.from({ length: n }, () => Array(n).fill(0));

for (let i = 0; i < n; i++) {
  for (let j = 0; j < n; j++) {
    const xi = rows.map(r => r[corrFields[i].key]);
    const xj = rows.map(r => r[corrFields[j].key]);
    const r = pearsonCorrelation(xi, xj);
    matrix[i][j] = +r.toFixed(4);
  }
}

fs.writeFileSync(path.join(OUTPUT_DIR, 'correlation.json'), JSON.stringify({ labels, matrix }, null, 2));
console.log('  -> correlation.json');

// ===== 5. Feature Importance =====
console.log('Computing feature importance...');

const featureFields = [
  { key: 'sst', name: '海温', desc: '海表温度影响藻类代谢速率和生长周期，20-28°C是多数赤潮藻种的最适温度区间' },
  { key: 'chlorophyll', name: '叶绿素', desc: '叶绿素是浮游植物生物量的直接指标，浓度越高赤潮发生可能性越大' },
  { key: 'wind_speed', name: '风速', desc: '风速影响水体混合和表层藻类聚集，低风速有利赤潮形成' },
  { key: 'pressure', name: '气压', desc: '气压变化反映天气系统变化，影响海洋水体稳定性' },
  { key: 'solar_radiation', name: '太阳辐射', desc: '光照是藻类光合作用的必要条件，充足光照促进藻类生长' },
  { key: 'precipitation', name: '降水量', desc: '降水带来陆源营养盐输入，可能加剧近岸水体富营养化' },
  { key: 'salinity', name: '盐度', desc: '盐度影响藻类细胞渗透压调节，河口区盐度变化与赤潮风险相关' },
  { key: 'nitrate', name: '硝酸盐', desc: '硝酸盐是浮游植物生长必需的氮源，浓度过高易引发赤潮' },
  { key: 'phosphate', name: '磷酸盐', desc: '磷酸盐是藻类生长的关键限制因子，与赤潮发生密切相关' },
  { key: 'silicate', name: '硅酸盐', desc: '硅酸盐是硅藻生长的必需元素，影响藻类种群结构' },
];

const rtLabels = rows.map(r => r.red_tide_label);
const featureImportance = featureFields.map(f => {
  const vals = rows.map(r => r[f.key]);
  const corr = pearsonCorrelation(vals, rtLabels);
  return {
    feature: f.name,
    importance: +Math.abs(corr).toFixed(4),
    correlation: +corr.toFixed(4),
    description: f.desc,
  };
});
featureImportance.sort((a, b) => b.importance - a.importance);

// Normalize to sum to 1
const totalImp = featureImportance.reduce((s, f) => s + f.importance, 0) || 1;
featureImportance.forEach(f => { f.importance = +(f.importance / totalImp).toFixed(4); });

fs.writeFileSync(path.join(OUTPUT_DIR, 'feature_importance.json'), JSON.stringify(featureImportance, null, 2));
console.log('  -> feature_importance.json');

// ===== 6. Paginated Samples =====
console.log('Exporting paginated samples...');

const totalPages = Math.ceil(rows.length / SAMPLES_PER_PAGE);
const indexEntry = { total_records: rows.length, per_page: SAMPLES_PER_PAGE, total_pages: totalPages, fields: Object.keys(rows[0]) };

for (let p = 0; p < totalPages; p++) {
  const start = p * SAMPLES_PER_PAGE;
  const end = Math.min(start + SAMPLES_PER_PAGE, rows.length);
  const pageData = rows.slice(start, end);
  const fname = `samples_${String(p + 1).padStart(4, '0')}.json`;
  fs.writeFileSync(path.join(OUTPUT_DIR, fname), JSON.stringify(pageData, null, 2));
  if (p % 20 === 0) process.stdout.write(`  page ${p + 1}/${totalPages}...\r`);
}
console.log(`  -> samples_*.json (${totalPages} pages, ${SAMPLES_PER_PAGE} per page)`);

fs.writeFileSync(path.join(OUTPUT_DIR, 'samples_index.json'), JSON.stringify(indexEntry, null, 2));
console.log('  -> samples_index.json');

// ===== 7. Organism summary =====
console.log('Computing organism summary...');

const organismMap = new Map();
for (const r of rows) {
  if (r.red_tide_organism) {
    const org = r.red_tide_organism.trim();
    if (!organismMap.has(org)) organismMap.set(org, { count: 0, toxicity_sum: 0, toxicity_count: 0 });
    const entry = organismMap.get(org);
    entry.count++;
    if (r.red_tide_toxicity >= 0) {
      entry.toxicity_sum += r.red_tide_toxicity;
      entry.toxicity_count++;
    }
  }
}

const organisms = [];
for (const [name, info] of organismMap) {
  organisms.push({
    name,
    count: info.count,
    avg_toxicity: info.toxicity_count > 0 ? +(info.toxicity_sum / info.toxicity_count).toFixed(2) : null,
  });
}
organisms.sort((a, b) => b.count - a.count);

fs.writeFileSync(path.join(OUTPUT_DIR, 'organisms.json'), JSON.stringify(organisms, null, 2));
console.log(`  -> organisms.json (${organisms.length} species)`);

console.log('\nExport complete!');
