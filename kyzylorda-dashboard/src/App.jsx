import React, { useMemo, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Polyline,
  Marker,
  Popup,
  Rectangle,
  Tooltip,
  useMap
} from "react-leaflet";
import L from "leaflet";
import { events } from "./data/events.js";
import {
  AlertTriangle,
  Wrench,
  TrafficCone,
  MapPin,
  Clock,
  Radio,
  Search,
  Activity,
  CheckCircle2,
  Circle
} from "lucide-react";

const KYZYLORDA_CENTER = [44.8488, 65.4823];

const INCIDENT_COLORS = {
  emergency: "#f97316", // warning orange
  repair: "#facc15", // yellow
  road_work: "#ef4444" // red for road repairs layer
};

function createIncidentIcon(type, isHovered, status) {
  const color = INCIDENT_COLORS[type] || INCIDENT_COLORS.emergency;
  const size = isHovered ? 18 : 14;
  const border = isHovered ? 3 : 2;
  
  // Add pulse animation for ongoing emergencies
  const pulseAnimation = type === "emergency" && status === "ongoing" 
    ? `
      <span style="
        position:absolute;
        top:0;
        left:0;
        width:${size}px;
        height:${size}px;
        border-radius:999px;
        background:${color};
        opacity:0.6;
        animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
      "></span>
      <style>
        @keyframes pulse {
          0%, 100% {
            transform: scale(1);
            opacity: 0.6;
          }
          50% {
            transform: scale(1.8);
            opacity: 0;
          }
        }
      </style>
    ` 
    : "";

  return L.divIcon({
    className: "",
    html: `<span style="position:relative;display:inline-block;width:${size}px;height:${size}px;">
        ${pulseAnimation}
        <span style="
          position:relative;
          display:inline-block;
          width:${size}px;
          height:${size}px;
          border-radius:999px;
          background:${color};
          box-shadow:0 0 0 ${border}px rgba(15,23,42,0.9),0 10px 30px rgba(15,23,42,0.7);
          border:1px solid rgba(15,23,42,0.6);
        "></span>
      </span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2]
  });
}

const typeConfig = {
  emergency: {
    label: "Аварийная ситуация",
    icon: AlertTriangle,
    color: "fill-warning-orange stroke-warning-orange"
  },
  repair: {
    label: "Ремонт",
    icon: Wrench,
    color: "fill-yellow-400/80 stroke-yellow-300"
  },
  road_work: {
    label: "Дорожные работы",
    icon: TrafficCone,
    color: "fill-electric-blue/70 stroke-electric-blue"
  }
};

function formatTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit"
    });
  } catch {
    return ts;
  }
}

function formatDate(ts) {
  try {
    return new Date(ts).toLocaleDateString([], {
      month: "short",
      day: "numeric"
    });
  } catch {
    return ts;
  }
}

function MapFocus({ target }) {
  const map = useMap();

  React.useEffect(() => {
    if (!target) return;
    const { lat, lng, polyline } = target;
    if (lat != null && lng != null) {
      map.flyTo([lat, lng], 14, { duration: 0.8 });
    } else if (polyline && polyline.length) {
      const latLngs = polyline.map(([lt, ln]) => [lt, ln]);
      map.fitBounds(latLngs, { padding: [60, 60] });
    }
  }, [target, map]);

  return null;
}

function App() {
  const [query, setQuery] = useState("");
  const [hoveredId, setHoveredId] = useState(null);
  const [focusedEvent, setFocusedEvent] = useState(null);
  const [incidentEvents, setIncidentEvents] = useState(events);
  const [searchResults, setSearchResults] = useState([]);
  const [searchHighlight, setSearchHighlight] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [newsText, setNewsText] = useState("");
  const [isParsingNews, setIsParsingNews] = useState(false);
  const [parseError, setParseError] = useState("");
  const [timelineValue, setTimelineValue] = useState(100);

  // WebSocket connection for real-time incident updates
  React.useEffect(() => {
    const ws = new WebSocket("wss://kyzylorda-dashboard-production.up.railway.app/ws");

    ws.onopen = () => {
      console.log("✓ WebSocket connected");
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "new_incident") {
          const data = message.data;
          console.log("📡 New incident received via WebSocket:", data);

          // Map to frontend event format
          const mappedType =
            data.event_type === "road_work"
              ? "road_work"
              : data.event_type === "repair"
              ? "repair"
              : "emergency";

          const newEvent = {
            id: `live-${Date.now()}`,
            type: mappedType,
            coordinates: data.coordinates || {},
            street: data.location || "Неизвестное местоположение",
            title: `${data.event_type || "Инцидент"} – ${data.location || "Кызылорда"}`,
            description: `Серьезность: ${data.severity || "неизвестно"}. Длительность: ${data.duration || "неизвестно"}.`,
            reportedBy: "Telegram канал",
            status: "ongoing",
            timestamp: new Date().toISOString()
          };

          // Geocode the location for accurate coordinates
          if (data.location && data.coordinates?.lat && data.coordinates?.lng) {
            // Try geocoding first, but with timeout
            const geocodeTimeout = setTimeout(() => {
              console.warn("Geocoding timed out, using AI coordinates");
              setIncidentEvents((prev) => [newEvent, ...prev]);
              if (newEvent.coordinates.lat != null && newEvent.coordinates.lng != null) {
                setFocusedEvent(newEvent.coordinates);
                setHoveredId(newEvent.id);
              }
            }, 3000);

            fetch(
              `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(
                `${data.location}, Kyzylorda, Kazakhstan`
              )}`,
              { signal: AbortSignal.timeout(2500) }
            )
              .then((res) => res.json())
              .then((geoData) => {
                clearTimeout(geocodeTimeout);
                if (geoData[0]) {
                  newEvent.coordinates = {
                    lat: parseFloat(geoData[0].lat),
                    lng: parseFloat(geoData[0].lon)
                  };
                  console.log("✓ Geocoded:", newEvent.street, newEvent.coordinates);
                } else {
                  console.log("→ Using AI coordinates (street not found in OSM)");
                }
                // Add to map
                setIncidentEvents((prev) => [newEvent, ...prev]);
                if (newEvent.coordinates.lat != null && newEvent.coordinates.lng != null) {
                  setFocusedEvent(newEvent.coordinates);
                  setHoveredId(newEvent.id);
                }
              })
              .catch((err) => {
                clearTimeout(geocodeTimeout);
                console.log("→ Using AI coordinates (geocoding failed):", err.message);
                // Use AI coordinates if geocoding fails
                setIncidentEvents((prev) => [newEvent, ...prev]);
                if (newEvent.coordinates.lat != null && newEvent.coordinates.lng != null) {
                  setFocusedEvent(newEvent.coordinates);
                  setHoveredId(newEvent.id);
                }
              });
          } else {
            // No location or no AI coordinates, add anyway
            setIncidentEvents((prev) => [newEvent, ...prev]);
          }
        }
      } catch (err) {
        console.error("Failed to parse WebSocket message:", err);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    ws.onclose = () => {
      console.log("✗ WebSocket disconnected");
    };

    // Cleanup on unmount
    return () => {
      ws.close();
    };
  }, []);

  // Get min and max timestamps
  const timelineRange = useMemo(() => {
    if (incidentEvents.length === 0) return { min: Date.now(), max: Date.now() };
    const timestamps = incidentEvents.map((e) => new Date(e.timestamp).getTime());
    return {
      min: Math.min(...timestamps),
      max: Math.max(...timestamps)
    };
  }, [incidentEvents]);

  // Filter events by timeline
  const filteredEvents = useMemo(() => {
    const threshold = timelineRange.min + (timelineRange.max - timelineRange.min) * (timelineValue / 100);
    return incidentEvents.filter((evt) => new Date(evt.timestamp).getTime() <= threshold);
  }, [incidentEvents, timelineValue, timelineRange]);

  const sortedEvents = useMemo(
    () =>
      [...filteredEvents].sort(
        (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
      ),
    [filteredEvents]
  );

  React.useEffect(() => {
    if (!query.trim()) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    const controller = new AbortController();
    const handle = setTimeout(async () => {
      try {
        setIsSearching(true);
        const response = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=5&q=${encodeURIComponent(
            `Kyzylorda ${query}`
          )}`,
          {
            signal: controller.signal,
            headers: {
              "Accept-Language": "en"
            }
          }
        );
        if (!response.ok) return;
        const data = await response.json();
        setSearchResults(data);
      } catch {
        // ignore network errors for now
      } finally {
        setIsSearching(false);
      }
    }, 400);

    return () => {
      clearTimeout(handle);
      controller.abort();
    };
  }, [query]);

  const handleSuggestionClick = (result) => {
    setQuery(result.display_name || "");
    const lat = parseFloat(result.lat);
    const lng = parseFloat(result.lon);

    let bounds = null;
    if (Array.isArray(result.boundingbox) && result.boundingbox.length === 4) {
      const [south, north, west, east] = result.boundingbox.map((v) =>
        parseFloat(v)
      );
      bounds = [
        [south, west],
        [north, east]
      ];
    }

    setFocusedEvent({ lat, lng });
    setSearchHighlight(bounds ? { bounds } : null);
    setSearchResults([]);
  };

  const handleEventClick = (evt) => {
    setFocusedEvent(evt.coordinates);
    setHoveredId(evt.id);
  };

  const handleParseNews = async () => {
    if (!newsText.trim() || isParsingNews) return;
    try {
      setIsParsingNews(true);
      setParseError("");

      const response = await fetch("https://kyzylorda-dashboard-production.up.railway.app/parse-news", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ text: newsText })
      });

      if (!response.ok) {
        const errorBody = await response.text();
        throw new Error(
          `Backend error (${response.status}): ${errorBody || "unknown"}`
        );
      }

      const data = await response.json();

      // Geocode the location name to get accurate coordinates
      let coordinates = data.coordinates || {};
      if (data.location) {
        try {
          const geoResponse = await fetch(
            `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(
              `${data.location}, Kyzylorda, Kazakhstan`
            )}`
          );
          const geoData = await geoResponse.json();
          if (geoData[0]) {
            coordinates = {
              lat: parseFloat(geoData[0].lat),
              lng: parseFloat(geoData[0].lon)
            };
          }
        } catch (geoErr) {
          console.warn("Geocoding failed, using AI coordinates:", geoErr);
        }
      }

      const mappedType =
        data.event_type === "road_work"
          ? "road_work"
          : data.event_type === "repair"
          ? "repair"
          : "emergency";

      const newEvent = {
        id: `live-${Date.now()}`,
        type: mappedType,
        coordinates,
        street: data.location || "Неизвестное местоположение",
        title: data.event_type
          ? `${data.event_type} – ${data.location || "Кызылорда"}`
          : data.location || "Инцидент",
        description: `Серьезность: ${data.severity || "неизвестно"}. Длительность: ${
          data.duration || "неизвестно"
        }.`,
        reportedBy: "AI распознавание новостей",
        status: "ongoing",
        timestamp: new Date().toISOString()
      };

      setIncidentEvents((prev) => [newEvent, ...prev]);
      if (newEvent.coordinates.lat != null && newEvent.coordinates.lng != null) {
        setFocusedEvent(newEvent.coordinates);
        setHoveredId(newEvent.id);
      }
      setNewsText("");
    } catch (err) {
      setParseError(err.message || "Failed to parse news.");
    } finally {
      setIsParsingNews(false);
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-slate-950 text-slate-100">
      {/* Top search bar */}
      <div className="pointer-events-none absolute inset-x-0 top-4 z-20 flex justify-center px-4">
        <div className="pointer-events-auto glass-panel flex max-w-2xl flex-1 items-center gap-2 rounded-xl px-3.5 py-2 shadow-[0_0_35px_rgba(59,130,246,0.15)]">
          <Search className="h-3.5 w-3.5 text-slate-300" />
          <input
            type="text"
            placeholder="Поиск улиц в Кызылорде (напр. Коркыт Ата, Айтеке би)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-transparent text-sm text-slate-50 placeholder:text-slate-500 focus:outline-none"
          />
          <span className="hidden text-[9px] uppercase tracking-[0.16em] text-slate-500 sm:inline">
            Система мониторинга города
          </span>
        </div>
      </div>

      {/* Suggestion dropdown */}
      {searchResults.length > 0 && (
        <div className="pointer-events-none absolute inset-x-0 top-16 z-20 flex justify-center px-4">
          <div className="pointer-events-auto glass-panel w-full max-w-3xl rounded-2xl p-2 text-sm shadow-[0_0_40px_rgba(59,130,246,0.15)]">
            {searchResults.map((result) => (
              <button
                key={`${result.place_id}-${result.osm_id}`}
                onClick={() => handleSuggestionClick(result)}
                className="flex w-full items-center justify-between rounded-xl px-3 py-1.5 text-left text-slate-100 hover:bg-slate-800/80"
              >
                <span className="flex flex-col">
                  <span>{result.display_name}</span>
                  {result.type && (
                    <span className="text-[11px] text-slate-500">
                      {result.type}
                    </span>
                  )}
                </span>
                <span className="flex items-center gap-1 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                  <MapPin className="h-3 w-3 text-electric-blue" />
                  Показать
                </span>
              </button>
            ))}
            {isSearching && (
              <div className="mt-1 px-2 text-[11px] text-slate-500">
                Поиск на карте...
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main layout */}
      <div className="relative flex h-full flex-col lg:flex-row">
        {/* Glassmorphism sidebar - scrollable */}
        <aside className="relative z-10 flex h-[40vh] w-full flex-col border-b border-slate-800/60 bg-gradient-to-b from-slate-950/95 via-slate-950/80 to-slate-950/95 px-4 py-4 backdrop-blur-xl lg:h-full lg:w-[380px] lg:border-b-0 lg:border-r lg:py-6 xl:w-[420px]">
          <div className="glass-panel flex h-full flex-col overflow-hidden rounded-3xl p-4 shadow-[0_0_60px_rgba(59,130,246,0.12)] sm:p-5">
            <header className="mb-4 flex shrink-0 items-center justify-between gap-3 border-b border-slate-800/60 pb-4">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-electric-blue">
                  Кызылорда Онлайн
                </p>
                <h1 className="text-lg font-semibold text-slate-50 sm:text-xl">
                  Центр управления инцидентами
                </h1>
              </div>
              <div className="flex items-center gap-2 rounded-2xl bg-electric-blue/15 px-3 py-1 ring-1 ring-electric-blue/30">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-electric-blue/70 opacity-70" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-electric-blue" />
                </span>
                <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-electric-blue">
                  Онлайн
                </span>
              </div>
            </header>

            <div className="mb-3 flex shrink-0 items-center gap-2 text-xs text-slate-400">
              <Radio className="h-3.5 w-3.5 text-warning-orange" />
              <span>
                Мониторинг{" "}
                <span className="text-slate-200">
                  {incidentEvents.length} активных
                </span>{" "}
                событий · {filteredEvents.length} показано
              </span>
            </div>

            <div className="mb-3 flex shrink-0 flex-wrap gap-2 text-[11px]">
              {Object.entries(typeConfig).map(([key, cfg]) => {
                const Icon = cfg.icon;
                const count = filteredEvents.filter((e) => e.type === key).length;
                return (
                  <div
                    key={key}
                    className="inline-flex items-center gap-1 rounded-full bg-slate-900/80 px-2.5 py-1 ring-1 ring-slate-800/60"
                  >
                    <Icon className="h-3 w-3 text-slate-300" />
                    <span className="text-slate-300">{cfg.label}</span>
                    <span className="text-slate-500">· {count}</span>
                  </div>
                );
              })}
            </div>

            {/* News parser input */}
            <div className="mb-3 shrink-0 space-y-2 rounded-2xl border border-electric-blue/20 bg-slate-950/50 p-3 shadow-inner">
              <p className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-electric-blue">
                <Activity className="h-3 w-3" />
                AI Парсер новостей
              </p>
              <textarea
                rows={3}
                value={newsText}
                onChange={(e) => setNewsText(e.target.value)}
                placeholder="Вставьте текст сообщения об инциденте..."
                className="w-full resize-none rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs text-slate-100 placeholder:text-slate-600 focus:border-electric-blue focus:outline-none focus:ring-1 focus:ring-electric-blue/50"
              />
              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={handleParseNews}
                  disabled={isParsingNews || !newsText.trim()}
                  className="inline-flex items-center gap-2 rounded-full bg-electric-blue px-3.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-950 transition-all hover:bg-electric-blue/90 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-300"
                >
                  {isParsingNews ? "Обработка..." : "Распознать и добавить"}
                </button>
                {parseError && (
                  <span className="max-w-[180px] text-[10px] text-warning-orange">
                    {parseError}
                  </span>
                )}
              </div>
            </div>

            <div className="mb-2 h-px shrink-0 w-full bg-gradient-to-r from-transparent via-slate-700/70 to-transparent" />

            {/* Event list - scrollable */}
            <div className="flex-1 space-y-2 overflow-y-auto pr-1 scrollbar-thin scrollbar-track-slate-900/20 scrollbar-thumb-slate-700/40">
              {sortedEvents.map((evt) => {
                const cfg = typeConfig[evt.type];
                const Icon = cfg.icon;
                const isHovered = hoveredId === evt.id;
                return (
                  <button
                    key={evt.id}
                    onMouseEnter={() => setHoveredId(evt.id)}
                    onMouseLeave={() =>
                      setHoveredId((id) => (id === evt.id ? null : id))
                    }
                    onClick={() => handleEventClick(evt)}
                    className={`group flex w-full flex-col rounded-2xl border px-3.5 py-3 text-left transition-all ${
                      isHovered
                        ? "border-electric-blue/60 bg-slate-900/80 shadow-[0_0_20px_rgba(59,130,246,0.2)]"
                        : "border-slate-800/80 bg-slate-900/60 hover:border-slate-700"
                    }`}
                  >
                    <div className="mb-1 flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2">
                        <span
                          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-900/80 ring-1 ring-slate-700/80`}
                        >
                          <Icon className="h-3.5 w-3.5 text-warning-orange" />
                        </span>
                        <div className="flex flex-col">
                          <span className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
                            {cfg.label}
                          </span>
                          <span className="text-sm font-semibold text-slate-50">
                            {evt.street}
                          </span>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${
                            evt.status === "ongoing"
                              ? "bg-warning-orange/20 text-warning-orange ring-1 ring-warning-orange/30"
                              : "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30"
                          }`}
                        >
                          {evt.status === "ongoing" ? (
                            <Circle className="h-2 w-2 fill-current" />
                          ) : (
                            <CheckCircle2 className="h-2.5 w-2.5" />
                          )}
                          {evt.status === "ongoing" ? "В процессе" : "Решено"}
                        </span>
                        <span className="inline-flex items-center gap-1 rounded-full bg-slate-950/80 px-2 py-0.5 text-[11px] text-slate-400">
                          <Clock className="h-3 w-3" />
                          {formatTime(evt.timestamp)}
                        </span>
                      </div>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-300">
                      {evt.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        {/* Map */}
        <main className="relative z-0 flex-1">
          <MapContainer
            center={KYZYLORDA_CENTER}
            zoom={13}
            className="map-leaflet-container h-full w-full"
            zoomControl={false}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            <MapFocus target={focusedEvent} />

            {searchHighlight?.bounds && (
              <Rectangle
                bounds={searchHighlight.bounds}
                pathOptions={{
                  color: "#3b82f6",
                  weight: 2,
                  fillColor: "#3b82f6",
                  fillOpacity: 0.08
                }}
              />
            )}

            {filteredEvents.map((evt) => {
              const cfg = typeConfig[evt.type];
              const isHovered = hoveredId === evt.id;
              const colorClass =
                INCIDENT_COLORS[evt.type] || INCIDENT_COLORS.emergency;

              const { lat, lng, polyline } = evt.coordinates;

              return (
                <React.Fragment key={evt.id}>
                  {/* General incidents layer – point markers with custom icons */}
                  {lat != null && lng != null && (
                    <Marker
                      position={[lat, lng]}
                      icon={createIncidentIcon(evt.type, isHovered, evt.status)}
                      eventHandlers={{
                        click: () => handleEventClick(evt),
                        mouseover: () => setHoveredId(evt.id),
                        mouseout: () =>
                          setHoveredId((id) => (id === evt.id ? null : id))
                      }}
                    >
                      <Tooltip direction="top" offset={[0, -6]} opacity={0.95}>
                        <div className="flex flex-col gap-0.5 text-xs">
                          <span className="font-semibold text-slate-900">
                            {cfg.label}
                          </span>
                          <span className="text-slate-900/80">{evt.street}</span>
                          <span className="text-[10px] text-slate-700">
                            {formatTime(evt.timestamp)}
                          </span>
                        </div>
                      </Tooltip>
                      <Popup>
                        <div className="space-y-1 text-xs">
                          <div className="font-semibold text-slate-900">
                            {evt.title || cfg.label}
                          </div>
                          <div className="text-slate-800">{evt.description}</div>
                          <div className="text-[11px] text-slate-600">
                            Источник:{" "}
                            <span className="font-medium">
                              {evt.reportedBy || "Система мониторинга города"}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-[11px]">
                            <span className="text-slate-500">
                              {formatDate(evt.timestamp)} {formatTime(evt.timestamp)}
                            </span>
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-medium uppercase ${
                                evt.status === "ongoing"
                                  ? "bg-warning-orange/20 text-warning-orange"
                                  : "bg-emerald-500/20 text-emerald-600"
                              }`}
                            >
                              {evt.status === "ongoing" ? "В процессе" : "Решено"}
                            </span>
                          </div>
                        </div>
                      </Popup>
                    </Marker>
                  )}

                  {/* Road repairs layer – red polylines */}
                  {polyline && (
                    <Polyline
                      positions={polyline}
                      pathOptions={{
                        color: INCIDENT_COLORS.road_work,
                        weight: isHovered ? 6 : 4,
                        opacity: isHovered ? 0.9 : 0.7
                      }}
                      eventHandlers={{
                        click: () => handleEventClick(evt),
                        mouseover: () => setHoveredId(evt.id),
                        mouseout: () =>
                          setHoveredId((id) => (id === evt.id ? null : id))
                      }}
                    >
                      <Popup>
                        <div className="space-y-1 text-xs">
                          <div className="font-semibold text-slate-900">
                            {evt.title || "Сегмент дорожного ремонта"}
                          </div>
                          <div className="text-slate-800">{evt.description}</div>
                          <div className="text-[11px] text-slate-600">
                            Источник:{" "}
                            <span className="font-medium">
                              {evt.reportedBy || "Департамент дорожных работ Кызылорды"}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-[11px]">
                            <span className="text-slate-500">
                              {formatDate(evt.timestamp)} {formatTime(evt.timestamp)}
                            </span>
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-medium uppercase ${
                                evt.status === "ongoing"
                                  ? "bg-warning-orange/20 text-warning-orange"
                                  : "bg-emerald-500/20 text-emerald-600"
                              }`}
                            >
                              {evt.status === "ongoing" ? "В процессе" : "Решено"}
                            </span>
                          </div>
                        </div>
                      </Popup>
                    </Polyline>
                  )}
                </React.Fragment>
              );
            })}
          </MapContainer>
        </main>
      </div>

      {/* Timeline slider at bottom */}
      <div className="pointer-events-none absolute inset-x-0 bottom-3 z-20 flex justify-center px-4">
        <div className="pointer-events-auto glass-panel max-w-lg rounded-xl px-4 py-2.5 shadow-[0_0_35px_rgba(59,130,246,0.15)]">
          <div className="flex items-center gap-3">
            <span className="shrink-0 text-[10px] uppercase tracking-wider text-slate-400">
              Временная шкала
            </span>
            <div className="flex-1">
              <input
                type="range"
                min="0"
                max="100"
                value={timelineValue}
                onChange={(e) => setTimelineValue(Number(e.target.value))}
                className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-slate-800/60 accent-electric-blue focus:outline-none [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-electric-blue [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgba(59,130,246,0.5)]"
              />
            </div>
            <span className="shrink-0 text-[10px] tabular-nums text-electric-blue">
              {formatTime(
                new Date(
                  timelineRange.min +
                    (timelineRange.max - timelineRange.min) *
                      (timelineValue / 100)
                ).toISOString()
              )}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
