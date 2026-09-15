import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import DataProcessing from './pages/DataProcessing';
import RiskMap from './pages/RiskMap';
import Prediction from './pages/Prediction';
import ModelEvaluation from './pages/ModelEvaluation';
import PredictionComparison from './pages/PredictionComparison';
import FutureTrend from './pages/FutureTrend';
import FeatureImportance from './pages/FeatureImportance';
import Report from './pages/Report';
import Correlation from './pages/Correlation';
import DataImport from './pages/DataImport';

function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/data-processing" element={<DataProcessing />} />
          <Route path="/risk-map" element={<RiskMap />} />
          <Route path="/prediction" element={<Prediction />} />
          <Route path="/model-evaluation" element={<ModelEvaluation />} />
          <Route path="/prediction-comparison" element={<PredictionComparison />} />
          <Route path="/future-trend" element={<FutureTrend />} />
          <Route path="/feature-importance" element={<FeatureImportance />} />
          <Route path="/report" element={<Report />} />
          <Route path="/correlation" element={<Correlation />} />
          <Route path="/data-import" element={<DataImport />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}

export default App;
