import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { DroneData } from '../hooks/useSocketIO';

// Fix for default marker icons
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

interface DroneMapProps {
  drones: DroneData[];
}

// Component to handle auto-zoom to fit all drones
const AutoFitBounds: React.FC<{ drones: DroneData[] }> = ({ drones }) => {
  const map = useMap();

  useEffect(() => {
    const dronesWithPosition = drones.filter(d => d.position);
    
    if (dronesWithPosition.length > 0) {
      const bounds = L.latLngBounds(
        dronesWithPosition.map(d => [d.position!.lat, d.position!.lon])
      );
      
      // Add padding and fit bounds
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
    }
  }, [drones, map]);

  return null;
};

// Create custom colored markers for each drone
const createDroneIcon = (color: string, droneId: number) => {
  return L.divIcon({
    className: 'custom-drone-marker',
    html: `
      <div style="
        background-color: ${color};
        width: 30px;
        height: 30px;
        border-radius: 50%;
        border: 3px solid white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        color: white;
        font-size: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
      ">
        ${droneId}
      </div>
    `,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -15]
  });
};

const DroneMap: React.FC<DroneMapProps> = ({ drones }) => {
  const dronesWithPosition = drones.filter(d => d.position && d.connected);
  
  // Default center (will be overridden by AutoFitBounds)
  const defaultCenter: [number, number] = dronesWithPosition.length > 0
    ? [dronesWithPosition[0].position!.lat, dronesWithPosition[0].position!.lon]
    : [37.7749, -122.4194]; // San Francisco default

  return (
    <div className="h-96 rounded-lg overflow-hidden">
      {dronesWithPosition.length === 0 ? (
        <div className="h-full flex items-center justify-center bg-gray-700 text-gray-400">
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
                d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
              />
            </svg>
            <p className="text-lg font-medium">Waiting for GPS data...</p>
            <p className="text-sm mt-2">Connect drones to see positions</p>
          </div>
        </div>
      ) : (
        <MapContainer
          center={defaultCenter}
          zoom={13}
          style={{ height: '100%', width: '100%' }}
          zoomControl={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          <AutoFitBounds drones={dronesWithPosition} />
          
          {dronesWithPosition.map(drone => (
            <Marker
              key={drone.id}
              position={[drone.position!.lat, drone.position!.lon]}
              icon={createDroneIcon(drone.color, drone.id)}
            >
              <Popup>
                <div className="text-gray-900 min-w-[200px]">
                  <h3 className="font-bold text-lg mb-2" style={{ color: drone.color }}>
                    {drone.name}
                  </h3>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="font-medium">Status:</span>
                      <span>{drone.status}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-medium">Altitude:</span>
                      <span>{drone.altitude?.toFixed(1) || 'N/A'} m</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-medium">Speed:</span>
                      <span>{drone.ground_speed?.toFixed(1) || 'N/A'} m/s</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-medium">Heading:</span>
                      <span>{drone.heading?.toFixed(0) || 'N/A'}°</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-medium">Battery:</span>
                      <span>{drone.battery_percent || 'N/A'}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-medium">GPS Sats:</span>
                      <span>{drone.satellites || 'N/A'}</span>
                    </div>
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      )}
    </div>
  );
};

export default DroneMap;
