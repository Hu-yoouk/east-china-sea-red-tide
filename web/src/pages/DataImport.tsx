import { useState, useCallback, useRef, type DragEvent, type ChangeEvent } from 'react';
import { useData } from '../services/dataContext';
import { importSampleData, generateCSVTemplate } from '../services/importService';
import type { ImportResult } from '../types';

export default function DataImport() {
  const { stats, samplesIndex, refreshData } = useData();
  const [dragOver, setDragOver] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [previewData, setPreviewData] = useState<Record<string, unknown>[]>([]);
  const [imported, setImported] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (file: File) => {
    setResult(null);
    setPreviewData([]);
    setImported(false);

    try {
      const text = await file.text();
      const res = importSampleData(text, file.name);
      setResult(res);
      if (res.success && res.data) {
        setPreviewData(res.data.rawRecords.slice(0, 20) as unknown as Record<string, unknown>[]);
      }
    } catch (e) {
      setResult({
        success: false,
        rows: 0,
        errors: [`文件读取失败: ${e instanceof Error ? e.message : '未知错误'}`]
      });
    }
  }, []);

  const onDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const onDragOver = (e: DragEvent) => { e.preventDefault(); setDragOver(true); };
  const onDragLeave = () => setDragOver(false);

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleImport = async () => {
    if (result?.data) {
      await refreshData();
      setImported(true);
    }
  };

  const downloadTemplate = () => {
    const csv = generateCSVTemplate();
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '赤潮数据导入模板.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const isLoaded = stats != null;
  const totalRecords = stats?.total_samples ?? samplesIndex?.total_records ?? 0;
  const gridCells = stats?.unique_grid_cells ?? 0;

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="page-title">数据导入</h2>
        <p className="page-subtitle">上传 CSV 或 JSON 格式的监测数据，系统将自动计算风险评分并更新所有页面</p>
      </div>

      {/* Status bar */}
      <div className="flex items-center gap-4 px-4 py-3 rounded-lg bg-ocean-800/40 border border-ocean-700/30">
        <span className="text-sm text-gray-400">当前数据状态：</span>
        <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium ${isLoaded ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'}`}>
          <span className={`w-2 h-2 rounded-full ${isLoaded ? 'bg-green-400 animate-pulse' : 'bg-yellow-400'}`} />
          {isLoaded ? '真实监测数据' : '数据加载中...'}
        </span>
        <span className="text-xs text-gray-500 ml-auto">
          {totalRecords.toLocaleString()} 条记录 · {gridCells} 个监测网格
        </span>
      </div>

      {/* Upload area */}
      <div className="grid grid-cols-2 gap-5">
        <div
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={`relative flex flex-col items-center justify-center h-64 rounded-xl border-2 border-dashed cursor-pointer transition-all duration-200 ${
            dragOver
              ? 'border-cyan-400 bg-cyan-500/10 scale-[1.02]'
              : 'border-ocean-600/50 bg-ocean-800/20 hover:border-cyan-500/50 hover:bg-ocean-800/40'
          }`}
        >
          <input ref={fileInputRef} type="file" accept=".csv,.json" onChange={onFileChange} className="hidden" />
          <span className="text-5xl mb-3">{dragOver ? '📂' : '📁'}</span>
          <p className="text-sm text-gray-300 font-medium">拖拽文件到此处或点击选择</p>
          <p className="text-xs text-gray-500 mt-2">支持 CSV、JSON 格式，最大 50MB</p>
        </div>

        <div className="p-5 rounded-xl bg-ocean-800/20 border border-ocean-700/30">
          <h3 className="text-sm font-semibold text-cyan-300 mb-3">导入说明</h3>
          <div className="space-y-2 text-xs text-gray-400">
            <div className="flex items-start gap-2">
              <span className="text-cyan-400 mt-0.5">1.</span>
              <span>数据文件需包含以下必需字段：<br />
                <code className="text-cyan-400/80 bg-ocean-950/50 px-1.5 py-0.5 rounded text-[11px]">
                  year, month, longitude, latitude, chlorophyll, sst, salinity, nitrate, phosphate, silicate, wind_speed, pressure, solar_radiation, precipitation
                </code>
              </span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-cyan-400 mt-0.5">2.</span>
              <span>系统会自动计算风险评分和风险等级，无需在数据中提供</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-cyan-400 mt-0.5">3.</span>
              <span>当前系统已加载真实监测数据（integrated_database.db），可直接使用</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-cyan-400 mt-0.5">4.</span>
              <span>如需替换数据，上传新文件后点击"确认导入"即可</span>
            </div>
          </div>
          <div className="flex gap-3 mt-4">
            <button onClick={downloadTemplate} className="px-4 py-2 rounded-lg bg-ocean-700/50 text-gray-300 text-xs border border-ocean-600/50 hover:bg-ocean-700 transition-colors">
              下载 CSV 模板
            </button>
          </div>
        </div>
      </div>

      {/* Parse result */}
      {result && (
        <div className={`p-5 rounded-xl border ${result.success ? 'bg-green-500/5 border-green-500/30' : 'bg-red-500/5 border-red-500/30'}`}>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">{result.success ? '✅' : '❌'}</span>
            <h3 className="text-sm font-semibold text-gray-200">
              {result.success ? `解析成功 - 共 ${result.rows} 条记录` : '解析失败'}
            </h3>
          </div>

          {result.errors.length > 0 && (
            <div className="mt-2 space-y-1">
              {result.errors.slice(0, 10).map((err, i) => (
                <p key={i} className="text-xs text-red-400 flex items-start gap-1">
                  <span className="text-red-500 shrink-0">{'⚠'}</span> {err}
                </p>
              ))}
              {result.errors.length > 10 && (
                <p className="text-xs text-gray-500">...还有 {result.errors.length - 10} 条错误</p>
              )}
            </div>
          )}

          {result.success && !imported && (
            <button onClick={handleImport} className="mt-4 px-6 py-2.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-medium hover:shadow-lg hover:shadow-cyan-500/25 transition-all">
              确认导入数据
            </button>
          )}

          {imported && (
            <p className="mt-3 text-sm text-green-400 flex items-center gap-2">
              <span>{'✅'}</span> 数据已刷新，所有页面已更新
            </p>
          )}
        </div>
      )}

      {/* Preview table */}
      {previewData.length > 0 && (
        <div className="rounded-xl border border-ocean-700/30 overflow-hidden">
          <div className="px-5 py-3 bg-ocean-800/40 border-b border-ocean-700/30">
            <h3 className="text-sm font-semibold text-gray-200">数据预览（前 20 条）</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-ocean-800/30 text-gray-400">
                  {Object.keys(previewData[0]).slice(0, 10).map(key => (
                    <th key={key} className="px-3 py-2 text-left font-medium whitespace-nowrap">{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewData.map((row, i) => (
                  <tr key={i} className={`border-t border-ocean-700/20 ${i % 2 === 0 ? 'bg-ocean-900/10' : ''}`}>
                    {Object.values(row).slice(0, 10).map((val, j) => (
                      <td key={j} className="px-3 py-1.5 text-gray-300 whitespace-nowrap">{String(val)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
