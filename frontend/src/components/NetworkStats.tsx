import React from 'react';
import { DroneData } from '../hooks/useSocketIO';

interface NetworkStatsProps {
  drones: DroneData[];
}

const NetworkStats: React.FC<NetworkStatsProps> = ({ drones }) => {
  const getStatusIndicator = (value: number | null, thresholds: { good: number; warning: number }) => {
    if (value === null) return 'bg-gray-500';
    if (value <= thresholds.good) return 'bg-green-500';
    if (value <= thresholds.warning) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left py-3 px-4 font-semibold text-gray-300">Drone</th>
            <th className="text-left py-3 px-4 font-semibold text-gray-300">Status</th>
            <th className="text-right py-3 px-4 font-semibold text-gray-300">Latency (ms)</th>
            <th className="text-right py-3 px-4 font-semibold text-gray-300">Jitter (ms)</th>
            <th className="text-right py-3 px-4 font-semibold text-gray-300">Update Rate (Hz)</th>
            <th className="text-right py-3 px-4 font-semibold text-gray-300">Packets</th>
            <th className="text-right py-3 px-4 font-semibold text-gray-300">Throughput</th>
          </tr>
        </thead>
        <tbody>
          {drones.map((drone, index) => {
            // Calculate estimated throughput (rough estimate based on MAVLink packet size)
            const avgPacketSize = 30; // Average MAVLink packet ~30 bytes
            const throughputBps = drone.update_rate_hz && drone.update_rate_hz > 0
              ? drone.update_rate_hz * avgPacketSize * 8 // bits per second
              : null;
            const throughputKbps = throughputBps ? (throughputBps / 1000).toFixed(2) : 'N/A';

            return (
              <tr
                key={drone.id}
                className={`border-b border-gray-700 hover:bg-gray-750 transition-colors ${
                  index % 2 === 0 ? 'bg-gray-800' : 'bg-gray-850'
                }`}
              >
                {/* Drone Name */}
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: drone.color }}
                    ></div>
                    <span className="font-medium">{drone.name}</span>
                  </div>
                </td>

                {/* Connection Status */}
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        drone.connected ? 'bg-green-500' : 'bg-red-500'
                      }`}
                    ></div>
                    <span className={drone.connected ? 'text-green-400' : 'text-red-400'}>
                      {drone.connected ? 'Online' : 'Offline'}
                    </span>
                  </div>
                </td>

                {/* Latency */}
                <td className="py-3 px-4 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div
                      className={`w-2 h-2 rounded-full ${getStatusIndicator(
                        drone.latency_ms,
                        { good: 50, warning: 100 }
                      )}`}
                    ></div>
                    <span className="font-mono">
                      {drone.latency_ms !== null ? drone.latency_ms.toFixed(2) : 'N/A'}
                    </span>
                  </div>
                </td>

                {/* Jitter */}
                <td className="py-3 px-4 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div
                      className={`w-2 h-2 rounded-full ${getStatusIndicator(
                        drone.jitter_ms,
                        { good: 10, warning: 20 }
                      )}`}
                    ></div>
                    <span className="font-mono">
                      {drone.jitter_ms !== null ? drone.jitter_ms.toFixed(2) : 'N/A'}
                    </span>
                  </div>
                </td>

                {/* Update Rate */}
                <td className="py-3 px-4 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        drone.update_rate_hz && drone.update_rate_hz > 10
                          ? 'bg-green-500'
                          : 'bg-yellow-500'
                      }`}
                    ></div>
                    <span className="font-mono">
                      {drone.update_rate_hz !== null ? drone.update_rate_hz.toFixed(1) : 'N/A'}
                    </span>
                  </div>
                </td>

                {/* Packet Count */}
                <td className="py-3 px-4 text-right">
                  <span className="font-mono">
                    {drone.packet_count !== null ? drone.packet_count.toLocaleString() : 'N/A'}
                  </span>
                </td>

                {/* Throughput */}
                <td className="py-3 px-4 text-right">
                  <span className="font-mono">
                    {throughputKbps !== 'N/A' ? `${throughputKbps} kb/s` : 'N/A'}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-6 text-xs text-gray-400">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500"></div>
          <span>Good</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
          <span>Warning</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-red-500"></div>
          <span>Critical</span>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-700 rounded-lg p-3">
          <div className="text-xs text-gray-400 mb-1">Total Drones</div>
          <div className="text-2xl font-bold">{drones.length}</div>
        </div>
        <div className="bg-gray-700 rounded-lg p-3">
          <div className="text-xs text-gray-400 mb-1">Connected</div>
          <div className="text-2xl font-bold text-green-400">
            {drones.filter(d => d.connected).length}
          </div>
        </div>
        <div className="bg-gray-700 rounded-lg p-3">
          <div className="text-xs text-gray-400 mb-1">Avg Latency</div>
          <div className="text-2xl font-bold">
            {(() => {
              const latencies = drones
                .filter(d => d.latency_ms !== null)
                .map(d => d.latency_ms!);
              if (latencies.length === 0) return 'N/A';
              const avg = latencies.reduce((a, b) => a + b, 0) / latencies.length;
              return `${avg.toFixed(1)} ms`;
            })()}
          </div>
        </div>
        <div className="bg-gray-700 rounded-lg p-3">
          <div className="text-xs text-gray-400 mb-1">Total Packets</div>
          <div className="text-2xl font-bold">
            {drones
              .filter(d => d.packet_count !== null)
              .reduce((sum, d) => sum + (d.packet_count || 0), 0)
              .toLocaleString()}
          </div>
        </div>
      </div>
    </div>
  );
};

export default NetworkStats;
