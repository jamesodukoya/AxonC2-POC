import { useEffect, useState, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';

export interface DroneData {
  id: number;
  name: string;
  color: string;
  connected: boolean;
  position: {
    lat: number;
    lon: number;
    alt: number;
  } | null;
  battery_percent: number | null;
  battery_voltage: number | null;
  altitude: number | null;
  ground_speed: number | null;
  heading: number | null;
  satellites: number | null;
  gps_fix: number | null;
  latency_ms: number | null;
  jitter_ms: number | null;
  update_rate_hz: number | null;
  packet_count: number | null;
  // NEW: Add throughput metrics
  total_rate_hz: number | null;
  total_packet_count: number | null;
  filtered_packet_count: number | null;
  total_message_types: number | null;
  demo_message_types: number | null;
  status: string;
  mode: string;
}

export interface TelemetryUpdate {
  timestamp: number;
  drones: DroneData[];
}

interface UseSocketIOReturn {
  connected: boolean;
  telemetry: TelemetryUpdate | null;
  // NEW: Add drones by ID for easier access
  dronesById: Record<number, DroneData>;
  startStreaming: () => void;
  stopStreaming: () => void;
  streaming: boolean;
  disconnect: () => void;
  reconnect: () => void;
}

const SOCKET_URL = 'http://localhost:5000';

export const useSocketIO = (): UseSocketIOReturn => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [connected, setConnected] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [telemetry, setTelemetry] = useState<TelemetryUpdate | null>(null);
  const [dronesById, setDronesById] = useState<Record<number, DroneData>>({});

  useEffect(() => {
    // Create socket connection
    const newSocket = io(SOCKET_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5
    });

    // Connection event handlers
    newSocket.on('connect', () => {
      console.log('✅ Connected to backend');
      setConnected(true);
    });

    newSocket.on('disconnect', () => {
      console.log('❌ Disconnected from backend');
      setConnected(false);
      setStreaming(false);
    });

    newSocket.on('connection_response', (data) => {
      console.log('📡 Connection response:', data);
    });

    newSocket.on('streaming_status', (data) => {
      console.log('🎬 Streaming status:', data.streaming);
      setStreaming(data.streaming);
    });

    newSocket.on('telemetry_update', (data: TelemetryUpdate) => {
      // 🐛 DEBUG: Log what we receive
      console.log('📡 Telemetry update received:', {
        timestamp: new Date(data.timestamp * 1000).toISOString(),
        droneCount: data.drones.length,
        droneIds: data.drones.map(d => d.id)
      });

      // ✅ FIX 1: Create a new object reference to force React update
      const newTelemetry = {
        timestamp: data.timestamp,
        drones: [...data.drones] // Create new array
      };

      // ✅ FIX 2: Convert to object keyed by drone ID
      const newDronesById: Record<number, DroneData> = {};
      data.drones.forEach(drone => {
        // Deep clone each drone to ensure new references
        newDronesById[drone.id] = { ...drone };
      });

      // 🐛 DEBUG: Log state update
      console.log('🔄 Updating state with drones:', Object.keys(newDronesById));

      // Update both states
      setTelemetry(newTelemetry);
      setDronesById(newDronesById);
    });

    newSocket.on('connect_error', (error) => {
      console.error('❌ Connection error:', error);
    });

    setSocket(newSocket);

    // Cleanup
    return () => {
      console.log('🧹 Cleaning up socket connection');
      newSocket.close();
    };
  }, []);

  const startStreaming = useCallback(() => {
    if (socket && connected) {
      console.log('▶️  Starting telemetry stream');
      socket.emit('start_streaming');
      setStreaming(true);
    } else {
      console.warn('⚠️  Cannot start streaming: socket not connected');
    }
  }, [socket, connected]);

  const stopStreaming = useCallback(() => {
    if (socket && connected) {
      console.log('⏸️  Stopping telemetry stream');
      socket.emit('stop_streaming');
      setStreaming(false);
    }
  }, [socket, connected]);

  // Disconnect WebSocket entirely
  const disconnect = useCallback(() => {
    if (socket) {
      console.log('🔌 Disconnecting socket');
      socket.disconnect();
      setStreaming(false);
      setTelemetry(null);
      setDronesById({});
    }
  }, [socket]);

  // Reconnect WebSocket
  const reconnect = useCallback(() => {
    if (socket) {
      console.log('🔄 Reconnecting socket');
      socket.connect();
    }
  }, [socket]);

  return {
    connected,
    telemetry,
    dronesById, // NEW: Provide drones indexed by ID
    startStreaming,
    stopStreaming,
    streaming,
    disconnect,
    reconnect
  };
};