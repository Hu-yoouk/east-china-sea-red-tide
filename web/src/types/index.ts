// ===== 真实数据基础类型 =====

export type RiskLevel = '低风险' | '中风险' | '高风险' | '极高风险';

/** 原始数据记录（与 SQLite 导出字段一致） */
export interface RawDataRecord {
  id: number;
  sample_id: string;
  year: number;
  month: number;
  longitude: number;
  latitude: number;
  sst: number | null;
  chlorophyll: number | null;
  wind_speed: number;
  pressure: number;
  solar_radiation: number;
  precipitation: number;
  red_tide_label: 0 | 1;
  red_tide_area: number | null;
  red_tide_organism: string | null;
  red_tide_toxicity: number;
  salinity: number;
  nitrate: number;
  phosphate: number;
  silicate: number;
}

/** 网格单元聚合数据（地图用） */
export interface GeoFeature {
  longitude: number;
  latitude: number;
  sample_count: number;
  red_tide_count: number;
  red_tide_frequency: number;
  risk_score: number;
  risk_level: string;
  organisms: string[];
  avg_red_tide_area: number;
  avg_sst: number;
  avg_chlorophyll: number;
  avg_wind_speed: number;
  avg_pressure: number;
  avg_solar_radiation: number;
  avg_precipitation: number;
  avg_salinity: number;
  avg_nitrate: number;
  avg_phosphate: number;
  avg_silicate: number;
}

/** 月度时间序列 */
export interface MonthlyTimeSeries {
  year: number;
  month: number;
  total: number;
  red_tide_count: number;
  red_tide_rate: number;
  red_tide_area_total: number;
  avg_sst: number;
  avg_chlorophyll: number;
  avg_wind_speed: number;
  avg_pressure: number;
  avg_solar_radiation: number;
  avg_precipitation: number;
  avg_salinity: number;
  avg_nitrate: number;
  avg_phosphate: number;
  avg_silicate: number;
}

/** 概览统计 */
export interface DataStats {
  total_samples: number;
  red_tide_count: number;
  red_tide_rate: number;
  time_range: { from: string; to: string };
  spatial_extent: { lon_min: number; lon_max: number; lat_min: number; lat_max: number };
  unique_grid_cells: number;
  monthly_stats: MonthlyTimeSeries[];
  yearly_stats: { year: number; total: number; red_tide_count: number; red_tide_rate: number }[];
}

/** 时间序列点（图表用） */
export interface TimeSeriesPoint {
  date: string;
  riskIndex: number;
  chlorophyll: number;
  temperature: number;
  salinity: number;
  nitrate: number;
  phosphate: number;
}

/** 模型性能 */
export interface ModelPerformance {
  model: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  auc: number;
  runtime: number;
}

/** 特征重要性 */
export interface FeatureImportance {
  feature: string;
  importance: number;
  correlation: number;
  description: string;
}

/** 未来预测 */
export interface FuturePrediction {
  date: string;
  region?: string;
  longitude: number;
  latitude: number;
  predictedRisk: number;
  riskLevel: string;
  probability: number;
}

/** 预警条目 */
export interface WarningItem {
  date: string;
  location: string;
  riskLevel: string;
  suggestion: string;
}

/** 仪表盘统计 */
export interface DashboardStats {
  totalSamples: number;
  redTideCount: number;
  redTideRate: number;
  monitoredCells: number;
  timeRange: string;
  highRiskCells: number;
  lastUpdate: string;
}

/** 数据处理步骤 */
export interface DataProcessStep {
  step: number;
  name: string;
  desc: string;
  icon: string;
}

// ===== 风险模型类型 =====

export interface RiskInput {
  chlorophyll: number;
  sst: number;
  salinity: number;
  wind_speed: number;
  pressure: number;
  solar_radiation: number;
  precipitation: number;
  nitrate: number;
  phosphate: number;
  silicate: number;
}

export interface RiskFactor {
  factor: string;
  contribution: number;
  description: string;
}

export interface RiskOutput {
  riskScore: number;
  probability: number;
  riskLevel: RiskLevel;
  riskColor: string;
  mainFactors: RiskFactor[];
  suggestions: string[];
}

// ===== 数据导入相关类型 =====

export interface ImportResult {
  success: boolean;
  rows: number;
  errors: string[];
  data?: ImportPreviewData;
}

export interface ImportPreviewData {
  rawRecords: RawDataRecord[];
  geoFeatures: GeoFeature[];
}

export interface CorrelationMatrix {
  labels: string[];
  matrix: number[][];
}

// ===== 赤潮藻种 =====

export interface OrganismInfo {
  name: string;
  count: number;
  avg_toxicity: number | null;
}
