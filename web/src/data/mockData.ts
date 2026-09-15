import type { ModelPerformance, DashboardStats, DataProcessStep } from '../types';

// ===== 模型性能数据 =====
export const modelPerformance: ModelPerformance[] = [
  { model: 'Logistic Regression', accuracy: 0.782, precision: 0.756, recall: 0.721, f1: 0.738, auc: 0.812, runtime: 1.2 },
  { model: 'Random Forest', accuracy: 0.865, precision: 0.848, recall: 0.832, f1: 0.840, auc: 0.901, runtime: 3.8 },
  { model: 'XGBoost', accuracy: 0.892, precision: 0.876, recall: 0.858, f1: 0.867, auc: 0.928, runtime: 2.5 },
  { model: 'BP Neural Network', accuracy: 0.856, precision: 0.835, recall: 0.818, f1: 0.826, auc: 0.895, runtime: 15.3 },
  { model: 'LSTM', accuracy: 0.878, precision: 0.862, recall: 0.845, f1: 0.853, auc: 0.918, runtime: 28.7 },
];

// ===== 数据处理流程步骤 =====
export const dataProcessSteps: DataProcessStep[] = [
  { step: 1, name: '数据采集', desc: '多源海洋环境数据采集', icon: '📡' },
  { step: 2, name: '数据清洗', desc: '去除重复、无效和异常记录', icon: '🧹' },
  { step: 3, name: '缺失值处理', desc: 'KNN插补与时间序列填充', icon: '🔧' },
  { step: 4, name: '异常值检测', desc: '3σ原则与IQR方法结合检测', icon: '🔍' },
  { step: 5, name: '数据归一化', desc: 'Min-Max标准化至[0,1]区间', icon: '📏' },
  { step: 6, name: '特征选择', desc: '基于SHAP值与相关性分析', icon: '🎯' },
  { step: 7, name: '建模数据', desc: '构建训练集与测试集(7:3)', icon: '📊' },
];

// Fallback stats when real data is not loaded
export const fallbackDashboardStats: DashboardStats = {
  totalSamples: 46800,
  redTideCount: 0,
  redTideRate: 0,
  monitoredCells: 0,
  timeRange: '--',
  highRiskCells: 0,
  lastUpdate: new Date().toLocaleString('zh-CN'),
};
