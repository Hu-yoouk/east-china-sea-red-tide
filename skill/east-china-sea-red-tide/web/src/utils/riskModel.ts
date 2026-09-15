import type { RiskInput, RiskOutput, RiskFactor } from '../types';

function sigmoid(x: number): number {
  return 1 / (1 + Math.exp(-x));
}

export function predictRisk(input: RiskInput): RiskOutput {
  const { chlorophyll, sst, salinity, wind_speed, solar_radiation, pressure, nitrate, phosphate } = input;

  let score = 0;
  const factors: RiskFactor[] = [];

  // 叶绿素贡献 (0-25分)
  let chlScore = 0;
  if (chlorophyll < 2) chlScore = 2;
  else if (chlorophyll < 5) chlScore = 5;
  else if (chlorophyll < 10) chlScore = 10;
  else if (chlorophyll < 20) chlScore = 18;
  else chlScore = 25;
  score += chlScore;
  factors.push({
    factor: '叶绿素',
    contribution: chlScore,
    description: chlorophyll > 10
      ? '叶绿素浓度显著偏高，浮游植物大量繁殖，赤潮风险较高'
      : chlorophyll > 5
      ? '叶绿素浓度偏高，浮游植物密度增加'
      : '叶绿素浓度正常'
  });

  // 水温贡献 (0-15分)
  let tempScore = 0;
  if (sst >= 20 && sst <= 28) tempScore = 12;
  else if (sst >= 15 && sst < 20) tempScore = 8;
  else if (sst > 28 && sst <= 32) tempScore = 15;
  else tempScore = 3;
  score += tempScore;
  factors.push({
    factor: '水温',
    contribution: tempScore,
    description: sst >= 20 && sst <= 30
      ? `水温${sst}℃处于赤潮藻类适宜生长区间`
      : `水温${sst}℃，偏离最适生长区间`
  });

  // 盐度贡献 (0-10分)
  let salScore = 0;
  if (salinity >= 25 && salinity <= 33) salScore = 8;
  else if (salinity >= 20 && salinity < 25) salScore = 5;
  else if (salinity > 33 && salinity <= 37) salScore = 6;
  else salScore = 2;
  score += salScore;
  factors.push({
    factor: '盐度',
    contribution: salScore,
    description: salinity >= 25 && salinity <= 33
      ? '盐度处于适宜范围，有利于赤潮藻类生长'
      : '盐度偏离最适范围'
  });

  // 风速贡献 (0-10分)
  let windScore = 0;
  if (wind_speed < 3) windScore = 10;
  else if (wind_speed < 5) windScore = 7;
  else if (wind_speed < 8) windScore = 4;
  else windScore = 1;
  score += windScore;
  factors.push({
    factor: '风速',
    contribution: windScore,
    description: wind_speed < 5
      ? '风速较低，水体交换弱，利于藻类聚集'
      : '风速适中，水体交换较好'
  });

  // 太阳辐射贡献 (0-10分)
  let lightScore = 0;
  if (solar_radiation > 800) lightScore = 10;
  else if (solar_radiation > 500) lightScore = 7;
  else if (solar_radiation > 200) lightScore = 4;
  else lightScore = 1;
  score += lightScore;
  factors.push({
    factor: '太阳辐射',
    contribution: lightScore,
    description: solar_radiation > 500
      ? '光照充足，有利于藻类光合作用'
      : '光照强度一般'
  });

  // 气压贡献 (0-5分)
  let pressureScore = 0;
  if (pressure < 1005) pressureScore = 5;
  else if (pressure < 1010) pressureScore = 3;
  else pressureScore = 1;
  score += pressureScore;
  factors.push({
    factor: '气压',
    contribution: pressureScore,
    description: pressure < 1005
      ? '气压偏低，可能伴随天气变化，影响水体稳定性'
      : '气压正常'
  });

  // 硝酸盐贡献 (0-10分)
  let nitrateScore = 0;
  if (nitrate > 20) nitrateScore = 10;
  else if (nitrate > 10) nitrateScore = 7;
  else if (nitrate > 5) nitrateScore = 4;
  else nitrateScore = 1;
  score += nitrateScore;
  factors.push({
    factor: '硝酸盐',
    contribution: nitrateScore,
    description: nitrate > 10
      ? '硝酸盐浓度高，为藻类生长提供充足氮源'
      : '硝酸盐浓度正常'
  });

  // 磷酸盐贡献 (0-10分)
  let phosphateScore = 0;
  if (phosphate > 2) phosphateScore = 10;
  else if (phosphate > 1) phosphateScore = 7;
  else if (phosphate > 0.5) phosphateScore = 4;
  else phosphateScore = 1;
  score += phosphateScore;
  factors.push({
    factor: '磷酸盐',
    contribution: phosphateScore,
    description: phosphate > 1
      ? '磷酸盐浓度偏高，藻类生长关键限制因子'
      : '磷酸盐浓度正常'
  });

  score = Math.min(100, Math.max(0, Math.round(score)));

  const probability = sigmoid((score - 40) / 12) * 100;

  let riskLevel: RiskOutput['riskLevel'];
  let riskColor: string;
  if (score <= 25) { riskLevel = '低风险'; riskColor = '#22c55e'; }
  else if (score <= 50) { riskLevel = '中风险'; riskColor = '#eab308'; }
  else if (score <= 75) { riskLevel = '高风险'; riskColor = '#f97316'; }
  else { riskLevel = '极高风险'; riskColor = '#ef4444'; }

  const sortedFactors = factors.sort((a, b) => b.contribution - a.contribution);
  const mainFactors = sortedFactors.slice(0, 4);

  const suggestions: string[] = [];
  if (score >= 51) {
    suggestions.push('加强赤潮监测频次，每日进行现场采样分析');
    suggestions.push('关注藻类优势种变化，警惕有毒藻种爆发');
    suggestions.push('提前做好应急响应准备，储备赤潮防控物资');
  } else if (score >= 26) {
    suggestions.push('保持常规监测频次，关注关键指标变化趋势');
    suggestions.push('加强卫星遥感监测，追踪叶绿素空间分布');
    suggestions.push('做好水质预警信息发布准备');
  } else {
    suggestions.push('维持例行监测，关注季节性环境变化');
    suggestions.push('定期更新风险评估模型参数');
    suggestions.push('建立赤潮案例数据库，持续优化预警能力');
  }

  if (chlorophyll > 15) {
    suggestions.push('叶绿素浓度异常偏高，建议开展藻类种类鉴定');
  }
  if (nitrate > 15) {
    suggestions.push('硝酸盐偏高，建议监测营养盐浓度和有机污染指标');
  }
  if (wind_speed < 3 && score >= 41) {
    suggestions.push('风速低且风险较高，建议密切关注近岸藻类聚集情况');
  }

  return {
    riskScore: score,
    probability: Math.round(probability * 10) / 10,
    riskLevel,
    riskColor,
    mainFactors,
    suggestions: suggestions.slice(0, 5),
  };
}

export function getRiskLevelColor(level: string): string {
  switch (level) {
    case '低风险': return '#22c55e';
    case '中风险': return '#eab308';
    case '高风险': return '#f97316';
    case '极高风险': return '#ef4444';
    default: return '#6b7280';
  }
}
