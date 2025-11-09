import React, { useEffect, useState } from 'react';
import { useSocketIO, DroneData } from '../hooks/useSocketIO';
import DroneMap from './DroneMap';
import TelemetryCard from './TelemetryCard';
import MetricsChart from './MetricsChart';
import NetworkStats from './NetworkStats';

interface HistoricalData {
  [droneId: number]: {
    timestamps: number[];
    latency: number[];
    jitter: number[];
    updateRate: number[];
  };
}

const Dashboard: React.FC = () => {
  const { connected, telemetry, startStreaming, stopStreaming, streaming, disconnect, reconnect } = useSocketIO();
  const [historicalData, setHistoricalData] = useState<HistoricalData>({});
  const [selectedMetric, setSelectedMetric] = useState<'latency' | 'jitter' | 'updateRate'>('latency');

  // Auto-start streaming when connected
  useEffect(() => {
    if (connected && !streaming) {
      startStreaming();
    }
  }, [connected, streaming, startStreaming]);

  // Update historical data for charts
  useEffect(() => {
    if (!telemetry) return;

    setHistoricalData(prev => {
      const updated = { ...prev };
      const maxPoints = 100;

      telemetry.drones.forEach(drone => {
        // Initialize if doesn't exist
        if (!updated[drone.id]) {
          updated[drone.id] = {
            timestamps: [],
            latency: [],
            jitter: [],
            updateRate: []
          };
        }

        const droneData = updated[drone.id];

        // ✅ Create NEW arrays instead of mutating
        let newTimestamps = [...droneData.timestamps, telemetry.timestamp];
        let newLatency = [...droneData.latency, drone.latency_ms || 0];
        let newJitter = [...droneData.jitter, drone.jitter_ms || 0];
        let newUpdateRate = [...droneData.updateRate, drone.update_rate_hz || 0];

        // Trim to max points
        if (newTimestamps.length > maxPoints) {
          newTimestamps = newTimestamps.slice(-maxPoints);
          newLatency = newLatency.slice(-maxPoints);
          newJitter = newJitter.slice(-maxPoints);
          newUpdateRate = newUpdateRate.slice(-maxPoints);
        }

        // ✅ Assign new object with new array references
        updated[drone.id] = {
          timestamps: newTimestamps,
          latency: newLatency,
          jitter: newJitter,
          updateRate: newUpdateRate
        };
      });

      return updated;
    });
  }, [telemetry]);


  const drones: DroneData[] = telemetry?.drones || [];

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">PX4 Command & Control</h1>
            <p className="text-sm text-gray-400">Real-time Multi-Drone Dashboard</p>
            <p><a href='https://youtu.be/xUNpxMBmeog' target='_blank' className='underline text-orange-500'>Explainer video</a></p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <span className="text-sm">{connected ? 'Connected' : 'Disconnected'}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${streaming ? 'bg-blue-500 animate-pulse' : 'bg-gray-500'}`}></div>
              <span className="text-sm">{streaming ? 'Streaming' : 'Idle'}</span>
            </div>
            <button
              onClick={() => {
                if (connected && streaming) {
                  disconnect();  // Disconnect WebSocket
                } else if (!connected) {
                  reconnect();   // Reconnect WebSocket
                }
              }}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${connected && streaming
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-green-600 hover:bg-green-700'
                }`}
            >
              {connected && streaming ? 'Disconnect' : 'Connect'}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6">
        {/* Telemetry Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
          {drones.map(drone => (
            <TelemetryCard key={drone.id} drone={drone} />
          ))}
        </div>

        {/* Map and Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Map */}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h2 className="text-lg font-semibold mb-4">Live Drone Positions</h2>
            <DroneMap drones={drones} />
          </div>

          {/* Network Metrics Chart */}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Network Metrics</h2>
              <select
                value={selectedMetric}
                onChange={(e) => setSelectedMetric(e.target.value as any)}
                className="bg-gray-700 text-white rounded px-3 py-1 text-sm border border-gray-600"
              >
                <option value="latency">Latency (ms)</option>
                <option value="jitter">Jitter (ms)</option>
                <option value="updateRate">Update Rate (Hz)</option>
              </select>
            </div>
            <MetricsChart
              historicalData={historicalData}
              drones={drones}
              metric={selectedMetric}
            />
          </div>
        </div>

        {/* Network Statistics Table */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h2 className="text-lg font-semibold mb-4">Network Statistics</h2>
          <NetworkStats drones={drones} />
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 border-t border-gray-700 px-6 py-4 text-center text-sm text-gray-400">
        <p>PX4 Dashboard • MAVlink Telemetry • Oluwadara James Odukoya</p>
      </footer>
    </div>
  );
};

export default Dashboard;
