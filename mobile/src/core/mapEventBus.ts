import type { MapMarker } from "../types";

type Coord = { lat: number; lng: number };
type CoordCb = (coord: Coord) => void;
type MarkerCb = (marker: MapMarker) => void;

const longPressSubscribers = new Set<CoordCb>();
const markerPressSubscribers = new Set<MarkerCb>();

export const mapEventBus = {
  emitLongPress(coord: Coord): void {
    longPressSubscribers.forEach((cb) => cb(coord));
  },
  emitMarkerPress(marker: MapMarker): void {
    markerPressSubscribers.forEach((cb) => cb(marker));
  },
  subscribeLongPress(cb: CoordCb): void {
    longPressSubscribers.add(cb);
  },
  unsubscribeLongPress(cb: CoordCb): void {
    longPressSubscribers.delete(cb);
  },
  subscribeMarkerPress(cb: MarkerCb): void {
    markerPressSubscribers.add(cb);
  },
  unsubscribeMarkerPress(cb: MarkerCb): void {
    markerPressSubscribers.delete(cb);
  },
};

export function _resetForTests(): void {
  longPressSubscribers.clear();
  markerPressSubscribers.clear();
}
