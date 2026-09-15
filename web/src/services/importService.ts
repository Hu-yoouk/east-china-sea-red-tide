import type { RawDataRecord, GeoFeature, ImportResult } from '../types';

const REQUIRED_FIELDS = [
  'year', 'month', 'longitude', 'latitude', 'chlorophyll', 'sst',
  'salinity', 'wind_speed', 'pressure', 'solar_radiation', 'precipitation',
  'nitrate', 'phosphate', 'silicate',
] as const;

const FIELD_NAMES: Record<string, string> = {
  'year': '年份', 'month': '月份', 'longitude': '经度', 'latitude': '纬度',
  'chlorophyll': '叶绿素', 'sst': '海温', 'salinity': '盐度', 'wind_speed': '风速',
  'pressure': '气压', 'solar_radiation': '太阳辐射', 'precipitation': '降水量',
  'nitrate': '硝酸盐', 'phosphate': '磷酸盐', 'silicate': '硅酸盐',
};

function parseCSV(text: string): Record<string, string>[] {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) throw new Error('CSV文件至少需要包含表头和一行数据');
  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
  const rows: Record<string, string>[] = [];
  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',').map(v => v.trim().replace(/^"|"$/g, ''));
    if (values.length !== headers.length) {
      throw new Error(`第${i + 1}行列数不匹配：期望${headers.length}列，实际${values.length}列`);
    }
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => { row[h] = values[idx]; });
    rows.push(row);
  }
  return rows;
}

function parseJSON(text: string): Record<string, string>[] {
  const parsed = JSON.parse(text);
  if (Array.isArray(parsed)) return parsed;
  if (parsed.data && Array.isArray(parsed.data)) return parsed.data;
  if (parsed.records && Array.isArray(parsed.records)) return parsed.records;
  throw new Error('JSON格式错误：需要数组或包含data/records字段的对象');
}

function parseFile(text: string, fileName: string): Record<string, string>[] {
  if (fileName.endsWith('.json')) return parseJSON(text);
  if (fileName.endsWith('.csv')) return parseCSV(text);
  throw new Error('不支持的文件格式，请使用 CSV 或 JSON 文件');
}

function toNum(v: unknown, fallback: number = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function computeRiskScore(r: Record<string, string | number>): number {
  const chl = toNum(r.chlorophyll || r.chlorophyll_a);
  const sst = toNum(r.sst || r.water_temperature);
  const nitrate = toNum(r.nitrate);
  const phosphate = toNum(r.phosphate);
  const wind = toNum(r.wind_speed);
  const solar = toNum(r.solar_radiation || r.light_intensity);
  const sal = toNum(r.salinity);

  const chlScore = Math.min(1, chl / 30) * 30;
  const nutrientScore = Math.min(1, (nitrate * 0.4 + phosphate * 3) / 10) * 25;
  const tempScore = (sst >= 20 && sst <= 28) ? 15 : 5;
  const salScore = (sal >= 15 && sal <= 32) ? 10 : 3;
  const windScore = Math.max(0, (1 - wind / 15)) * 10;
  const solarScore = Math.min(1, solar / 300) * 10;

  return Math.min(100, Math.max(0, Math.round(
    chlScore + nutrientScore + tempScore + salScore + windScore + solarScore
  )));
}

function getRiskLevel(score: number): string {
  if (score <= 25) return '低风险';
  if (score <= 50) return '中风险';
  if (score <= 75) return '高风险';
  return '极高风险';
}

export function importSampleData(text: string, fileName: string): ImportResult {
  const errors: string[] = [];
  try {
    const rows = parseFile(text, fileName);
    if (rows.length === 0) {
      return { success: false, rows: 0, errors: ['文件中没有数据行'] };
    }

    const headers = Object.keys(rows[0]);
    const missingFields = REQUIRED_FIELDS.filter(f => !headers.includes(f));
    if (missingFields.length > 0) {
      return {
        success: false, rows: 0,
        errors: [`缺少必需字段: ${missingFields.map(f => FIELD_NAMES[f] || f).join('、')}`],
      };
    }

    const records: RawDataRecord[] = [];
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const line = i + 2;
      const record: RawDataRecord = {
        id: i + 1,
        sample_id: `IMPORT_${i + 1}`,
        year: toNum(row.year, 2026),
        month: toNum(row.month, 1),
        longitude: toNum(row.longitude),
        latitude: toNum(row.latitude),
        sst: row.sst != null && row.sst !== '' ? toNum(row.sst) : null,
        chlorophyll: row.chlorophyll != null && row.chlorophyll !== '' ? toNum(row.chlorophyll || row.chlorophyll_a) : null,
        wind_speed: toNum(row.wind_speed),
        pressure: toNum(row.pressure),
        solar_radiation: toNum(row.solar_radiation || row.light_intensity),
        precipitation: toNum(row.precipitation),
        red_tide_label: 0,
        red_tide_area: null,
        red_tide_organism: null,
        red_tide_toxicity: -1,
        salinity: toNum(row.salinity),
        nitrate: toNum(row.nitrate),
        phosphate: toNum(row.phosphate),
        silicate: toNum(row.silicate),
      };

      const riskScore = computeRiskScore(row);
      if (riskScore >= 50) record.red_tide_label = 1;

      records.push(record);

      if (!Number.isFinite(record.longitude) || !Number.isFinite(record.latitude)) {
        errors.push(`第${line}行: 经纬度无效`);
      }
    }

    if (errors.length > 0 && records.length === 0) {
      return { success: false, rows: 0, errors };
    }

    // Aggregate into geo features
    const geoMap = new Map<string, RawDataRecord[]>();
    for (const r of records) {
      const key = `${r.longitude}_${r.latitude}`;
      if (!geoMap.has(key)) geoMap.set(key, []);
      geoMap.get(key)!.push(r);
    }

    const geoFeatures: GeoFeature[] = [];
    for (const [, recs] of geoMap) {
      const rtCount = recs.filter(r => r.red_tide_label === 1).length;
      const avg = (fn: (r: RawDataRecord) => number) => {
        const vals = recs.map(fn).filter(v => v != null && Number.isFinite(v));
        return vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
      };
      geoFeatures.push({
        longitude: +(recs.reduce((s, r) => s + r.longitude, 0) / recs.length).toFixed(4),
        latitude: +(recs.reduce((s, r) => s + r.latitude, 0) / recs.length).toFixed(4),
        sample_count: recs.length,
        red_tide_count: rtCount,
        red_tide_frequency: recs.length > 0 ? rtCount / recs.length : 0,
        risk_score: Math.round((rtCount / recs.length) * 100),
        risk_level: getRiskLevel(Math.round((rtCount / recs.length) * 100)),
        organisms: [],
        avg_red_tide_area: 0,
        avg_sst: +avg(r => r.sst!).toFixed(4),
        avg_chlorophyll: +avg(r => r.chlorophyll!).toFixed(4),
        avg_wind_speed: +avg(r => r.wind_speed).toFixed(4),
        avg_pressure: +avg(r => r.pressure).toFixed(4),
        avg_solar_radiation: +avg(r => r.solar_radiation).toFixed(4),
        avg_precipitation: +avg(r => r.precipitation).toFixed(4),
        avg_salinity: +avg(r => r.salinity).toFixed(4),
        avg_nitrate: +avg(r => r.nitrate).toFixed(4),
        avg_phosphate: +avg(r => r.phosphate).toFixed(4),
        avg_silicate: +avg(r => r.silicate).toFixed(4),
      });
    }

    return {
      success: true,
      rows: records.length,
      errors: errors.length > 0 ? errors : [],
      data: { rawRecords: records, geoFeatures },
    };
  } catch (e) {
    return {
      success: false, rows: 0,
      errors: [`文件解析失败: ${e instanceof Error ? e.message : '未知错误'}`],
    };
  }
}

export function generateCSVTemplate(): string {
  const headers = REQUIRED_FIELDS as unknown as string[];
  const sampleRow = [
    '2026', '5', '120.5', '29.0', '15.3', '25.8', '28.7', '3.2', '1010.5',
    '280', '0.5', '3.5', '0.35', '6.8',
  ];
  return [headers.join(','), sampleRow.join(',')].join('\n');
}
