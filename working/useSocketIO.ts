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
      console.log('Connected to backend');
      setConnected(true);
    });

    newSocket.on('disconnect', () => {
      console.log('Disconnected from backend');
      setConnected(false);
      setStreaming(false);
    });

    newSocket.on('connection_response', (data) => {
      console.log('Connection response:', data);
    });

    newSocket.on('streaming_status', (data) => {
      console.log('Streaming status:', data.streaming);
      setStreaming(data.streaming);
    });

    newSocket.on('telemetry_update', (data: TelemetryUpdate) => {
      setTelemetry(data);
    });

    newSocket.on('connect_error', (error) => {
      console.error('Connection error:', error);
    });

    setSocket(newSocket);

    // Cleanup
    return () => {
      newSocket.close();
    };
  }, []);

  const startStreaming = useCallback(() => {
    if (socket && connected) {
      socket.emit('start_streaming');
      setStreaming(true);
    }
  }, [socket, connected]);

  const stopStreaming = useCallback(() => {
    if (socket && connected) {
      socket.emit('stop_streaming');
      setStreaming(false);
    }
  }, [socket, connected]);

  // NEW: Disconnect WebSocket entirely
  const disconnect = useCallback(() => {
    if (socket) {
      socket.disconnect();
      setStreaming(false);
      setTelemetry(null);
    }
  }, [socket]);

  // NEW: Reconnect WebSocket
  const reconnect = useCallback(() => {
    if (socket) {
      socket.connect();
    }
  }, [socket]);

  return {
    connected,
    telemetry,
    startStreaming,
    stopStreaming,
    streaming,
    disconnect,
    reconnect
  };
};
