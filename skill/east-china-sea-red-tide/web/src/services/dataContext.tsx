import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type {
  DataStats, GeoFeature, MonthlyTimeSeries, FeatureImportance,
  CorrelationMatrix, RawDataRecord, TimeSeriesPoint,
  FuturePrediction, WarningItem, DashboardStats, ModelPerformance, DataProcessStep,
} from '../types';
import { modelPerformance, dataProcessSteps } from '../data/mockData';

interface SamplesIndex {
  total_records: number;
  per_page: number;
  total_pages: number;
  fields: string[];
}

interface DataState {
  stats: DataStats | null;
  geoData: GeoFeature[];
  timeSeries: MonthlyTimeSeries[];
  featureImportance: FeatureImportance[];
  correlation: CorrelationMatrix | null;
  samplesIndex: SamplesIndex | null;
  timeSeriesPoints: TimeSeriesPoint[];
  futurePredictions: FuturePrediction[];
  warningList: WarningItem[];
  dashboardStats: DashboardStats | null;
  loading: boolean;
  error: string | null;
}

interface DataContextValue extends DataState {
  loadSamplePage: (page: number) => Promise<RawDataRecord[]>;
  refreshData: () => Promise<void>;
  modelPerformance: ModelPerformance[];
  dataProcessSteps: DataProcessStep[];
}

const BASE = import.meta.env.BASE_URL;

const DataContext = createContext<DataContextValue | null>(null);

function buildTimeSeriesPoints(monthly: MonthlyTimeSeries[]): TimeSeriesPoint[] {
  return monthly.map(m => ({
    date: `${m.year}-${String(m.month).padStart(2, '0')}`,
    riskIndex: Math.round(m.red_tide_rate * 100),
    chlorophyll: m.avg_chlorophyll,
    temperature: m.avg_sst,
    salinity: m.avg_salinity,
    nitrate: m.avg_nitrate,
    phosphate: m.avg_phosphate,
  }));
}

function buildFuturePredictions(_geoData: GeoFeature[], _timeSeries: MonthlyTimeSeries[]): FuturePrediction[] {
  return [];
}

function buildWarningList(geoData: GeoFeature[]): WarningItem[] {
  return geoData
    .filter(g => g.risk_score >= 50 && g.sample_count >= 5)
    .sort((a, b) => b.risk_score - a.risk_score)
    .slice(0, 15)
    .map(g => {
      const suggestions: Record<string, string> = {
        '高风险': '建议加强赤潮监测频次，开展藻种鉴定',
        '中风险': '保持常规监测，关注环境因子变化趋势',
      };
      return {
        date: '--',
        location: `${g.longitude.toFixed(2)}°E, ${g.latitude.toFixed(2)}°N`,
        riskLevel: g.risk_level,
        suggestion: suggestions[g.risk_level] || '维持例行监测',
      };
    });
}

function buildDashboardStats(stats: DataStats, geoData: GeoFeature[]): DashboardStats {
  const highRiskCells = geoData.filter(g => g.risk_score >= 50).length;
  return {
    totalSamples: stats.total_samples,
    redTideCount: stats.red_tide_count,
    redTideRate: +(stats.red_tide_rate * 100).toFixed(1),
    monitoredCells: stats.unique_grid_cells,
    timeRange: `${stats.time_range.from} ~ ${stats.time_range.to}`,
    highRiskCells,
    lastUpdate: new Date().toLocaleString('zh-CN'),
  };
}

export function DataProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DataState>({
    stats: null,
    geoData: [],
    timeSeries: [],
    featureImportance: [],
    correlation: null,
    samplesIndex: null,
    timeSeriesPoints: [],
    futurePredictions: [],
    warningList: [],
    dashboardStats: null,
    loading: true,
    error: null,
  });

  const loadData = useCallback(async () => {
    try {
      const [statsRes, geoRes, tsRes, fiRes, corrRes, idxRes] = await Promise.all([
        fetch(BASE + 'data/stats.json'),
        fetch(BASE + 'data/geo_data.json'),
        fetch(BASE + 'data/time_series.json'),
        fetch(BASE + 'data/feature_importance.json'),
        fetch(BASE + 'data/correlation.json'),
        fetch(BASE + 'data/samples_index.json'),
      ]);

      if (!statsRes.ok) throw new Error('Failed to load stats');

      const stats: DataStats = await statsRes.json();
      const geoData: GeoFeature[] = await geoRes.json();
      const timeSeries: MonthlyTimeSeries[] = await tsRes.json();
      const featureImportance: FeatureImportance[] = await fiRes.json();
      const correlation: CorrelationMatrix = await corrRes.json();
      const samplesIndex: SamplesIndex = await idxRes.json();

      const timeSeriesPoints = buildTimeSeriesPoints(timeSeries);
      const futurePredictions = buildFuturePredictions(geoData, timeSeries);
      const warningList = buildWarningList(geoData);
      const dashboardStats = buildDashboardStats(stats, geoData);

      setState({
        stats,
        geoData,
        timeSeries,
        featureImportance,
        correlation,
        samplesIndex,
        timeSeriesPoints,
        futurePredictions,
        warningList,
        dashboardStats,
        loading: false,
        error: null,
      });
    } catch (err) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : '数据加载失败',
      }));
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const loadSamplePage = useCallback(async (page: number): Promise<RawDataRecord[]> => {
    const fname = `samples_${String(page).padStart(4, '0')}.json`;
    const res = await fetch(BASE + `data/${fname}`);
    if (!res.ok) throw new Error(`Failed to load page ${page}`);
    return res.json();
  }, []);

  return (
    <DataContext.Provider value={{ ...state, loadSamplePage, refreshData: loadData, modelPerformance, dataProcessSteps }}>
      {children}
    </DataContext.Provider>
  );
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be used within DataProvider');
  return ctx;
}
