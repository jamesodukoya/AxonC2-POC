import React from 'react';
import { DroneData } from '../hooks/useSocketIO';

interface TelemetryCardProps {
  drone: DroneData;
}

const TelemetryCard: React.FC<TelemetryCardProps> = ({ drone }) => {
  const getBatteryColor = (percent: number | null): string => {
    if (!percent) return 'bg-gray-500';
    if (percent > 50) return 'bg-green-500';
    if (percent > 20) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getStatusColor = (status: string): string => {
    const statusColors: { [key: string]: string } = {
      'Active': 'bg-green-500',
      'Standby': 'bg-blue-500',
      'Critical': 'bg-red-500',
      'Emergency': 'bg-red-600',
      'Boot': 'bg-yellow-500',
      'Calibrating': 'bg-yellow-500'
    };
    return statusColors[status] || 'bg-gray-500';
  };

  const getGPSFixText = (fixType: number | null): string => {
    if (!fixType) return 'No Fix';
    const fixTypes: { [key: number]: string } = {
      0: 'No Fix',
      1: 'No Fix',
      2: '2D Fix',
      3: '3D Fix',
      4: 'DGPS',
      5: 'RTK Float',
      6: 'RTK Fixed'
    };
    return fixTypes[fixType] || 'Unknown';
  };

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div
        className="px-4 py-3 font-bold text-lg flex items-center justify-between"
        style={{ backgroundColor: drone.color }}
      >
        <span>{drone.name}</span>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${drone.connected ? 'bg-white animate-pulse' : 'bg-gray-400'}`}></div>
          <span className="text-sm font-normal">
            {drone.connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Status */}
        <div className="flex items-center justify-between">
          <span className="text-gray-400 text-sm">Status</span>
          <span className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${getStatusColor(drone.status)}`}></div>
            <span className="font-medium">{drone.status}</span>
          </span>
        </div>

        {/* Battery */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-gray-400 text-sm">Battery</span>
            <span className="font-medium">
              {drone.battery_percent !== null ? `${drone.battery_percent}%` : 'N/A'}
            </span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all ${getBatteryColor(drone.battery_percent)}`}
              style={{ width: `${drone.battery_percent || 0}%` }}
            ></div>
          </div>
          {drone.battery_voltage && (
            <span className="text-xs text-gray-500 mt-1 block">
              {drone.battery_voltage.toFixed(2)}V
            </span>
          )}
        </div>

        {/* Position */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm">Latitude</span>
            <span className="font-mono text-sm">
              {drone.position ? drone.position.lat.toFixed(6) : 'N/A'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm">Longitude</span>
            <span className="font-mono text-sm">
              {drone.position ? drone.position.lon.toFixed(6) : 'N/A'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm">Altitude</span>
            <span className="font-medium">
              {drone.altitude !== null ? `${drone.altitude.toFixed(1)} m` : 'N/A'}
            </span>
          </div>
        </div>

        {/* Flight Data */}
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-700">
          <div>
            <div className="text-gray-400 text-xs mb-1">Speed</div>
            <div className="font-medium text-sm">
              {drone.ground_speed !== null ? `${drone.ground_speed.toFixed(1)} m/s` : 'N/A'}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-xs mb-1">Heading</div>
            <div className="font-medium text-sm">
              {drone.heading !== null ? `${drone.heading.toFixed(0)}°` : 'N/A'}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-xs mb-1">GPS</div>
            <div className="font-medium text-sm">
              {getGPSFixText(drone.gps_fix)}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-xs mb-1">Satellites</div>
            <div className="font-medium text-sm">
              {drone.satellites !== null ? drone.satellites : 'N/A'}
            </div>
          </div>
        </div>

        {/* Network Metrics */}
        <div className="pt-2 border-t border-gray-700">
          <div className="text-gray-400 text-xs mb-2">Network Metrics</div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <div className="text-gray-500">Latency</div>
              <div className="font-medium">
                {drone.latency_ms !== null ? `${drone.latency_ms.toFixed(1)} ms` : 'N/A'}
              </div>
            </div>
            <div>
              <div className="text-gray-500">Jitter</div>
              <div className="font-medium">
                {drone.jitter_ms !== null ? `${drone.jitter_ms.toFixed(1)} ms` : 'N/A'}
              </div>
            </div>
            <div>
              <div className="text-gray-500">Rate</div>
              <div className="font-medium">
                {drone.update_rate_hz !== null ? `${drone.update_rate_hz.toFixed(0)} Hz` : 'N/A'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TelemetryCard;
