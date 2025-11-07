import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { DroneData } from '../hooks/useSocketIO';

interface MetricsChartProps {
  historicalData: {
    [droneId: number]: {
      timestamps: number[];
      latency: number[];
      jitter: number[];
      updateRate: number[];
    };
  };
  drones: DroneData[];
  metric: 'latency' | 'jitter' | 'updateRate';
}

const MetricsChart: React.FC<MetricsChartProps> = ({ historicalData, drones, metric }) => {
  // Transform data for Recharts
  const chartData = React.useMemo(() => {
    // Find the longest data series
    let maxLength = 0;
    Object.values(historicalData).forEach(data => {
      maxLength = Math.max(maxLength, data.timestamps.length);
    });

    if (maxLength === 0) return [];

    // Build chart data
    const data: any[] = [];
    for (let i = 0; i < maxLength; i++) {
      const point: any = { index: i };
      
      drones.forEach(drone => {
        const droneData = historicalData[drone.id];
        if (droneData && i < droneData.timestamps.length) {
          const metricValue = 
            metric === 'latency' ? droneData.latency[i] :
            metric === 'jitter' ? droneData.jitter[i] :
            droneData.updateRate[i];
          
          point[`drone${drone.id}`] = metricValue;
        }
      });
      
      data.push(point);
    }
    
    return data;
  }, [historicalData, drones, metric]);

  const getMetricLabel = () => {
    switch (metric) {
      case 'latency': return 'Latency (ms)';
      case 'jitter': return 'Jitter (ms)';
      case 'updateRate': return 'Update Rate (Hz)';
    }
  };

  const getYAxisDomain = () => {
    switch (metric) {
      case 'latency': return [0, 100];
      case 'jitter': return [0, 30];
      case 'updateRate': return [0, 50];
    }
  };

  if (chartData.length === 0) {
    return (
      <div className="h-72 flex items-center justify-center text-gray-400">
        <div className="text-center">
          <svg
            className="mx-auto h-12 w-12 mb-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
          <p>Waiting for metrics data...</p>
        </div>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart
        data={chartData}
        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis
          dataKey="index"
          stroke="#9CA3AF"
          label={{ value: 'Time', position: 'insideBottomRight', offset: -5, fill: '#9CA3AF' }}
        />
        <YAxis
          stroke="#9CA3AF"
          domain={getYAxisDomain()}
          label={{ value: getMetricLabel(), angle: -90, position: 'insideLeft', fill: '#9CA3AF' }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#1F2937',
            border: '1px solid #374151',
            borderRadius: '0.5rem',
            color: '#F3F4F6'
          }}
          formatter={(value: number) => value.toFixed(2)}
        />
        <Legend
          wrapperStyle={{ color: '#F3F4F6' }}
          formatter={(value) => {
            const droneId = parseInt(value.replace('drone', ''));
            const drone = drones.find(d => d.id === droneId);
            return drone ? drone.name : value;
          }}
        />
        {drones.map(drone => (
          <Line
            key={drone.id}
            type="monotone"
            dataKey={`drone${drone.id}`}
            stroke={drone.color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
};

export default MetricsChart;
