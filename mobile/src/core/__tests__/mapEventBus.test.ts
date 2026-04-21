import { mapEventBus } from "../mapEventBus";

afterEach(() => {
  // Reset module-level sets between tests by unsubscribing all added callbacks
});

describe("mapEventBus", () => {
  it("calls long-press subscribers with the coord", () => {
    const cb = jest.fn();
    mapEventBus.subscribeLongPress(cb);
    mapEventBus.emitLongPress({ lat: 1.23, lng: 4.56 });
    expect(cb).toHaveBeenCalledWith({ lat: 1.23, lng: 4.56 });
    mapEventBus.unsubscribeLongPress(cb);
  });

  it("does not call long-press subscriber after unsubscribe", () => {
    const cb = jest.fn();
    mapEventBus.subscribeLongPress(cb);
    mapEventBus.unsubscribeLongPress(cb);
    mapEventBus.emitLongPress({ lat: 0, lng: 0 });
    expect(cb).not.toHaveBeenCalled();
  });

  it("calls marker-press subscribers with the marker", () => {
    const cb = jest.fn();
    mapEventBus.subscribeMarkerPress(cb);
    const marker = { id: "m1", lat: 1, lng: 2, data: { source: "host" } };
    mapEventBus.emitMarkerPress(marker);
    expect(cb).toHaveBeenCalledWith(marker);
    mapEventBus.unsubscribeMarkerPress(cb);
  });

  it("does not call marker-press subscriber after unsubscribe", () => {
    const cb = jest.fn();
    mapEventBus.subscribeMarkerPress(cb);
    mapEventBus.unsubscribeMarkerPress(cb);
    mapEventBus.emitMarkerPress({ id: "m1", lat: 0, lng: 0 });
    expect(cb).not.toHaveBeenCalled();
  });

  it("calls multiple subscribers independently", () => {
    const cb1 = jest.fn();
    const cb2 = jest.fn();
    mapEventBus.subscribeLongPress(cb1);
    mapEventBus.subscribeLongPress(cb2);
    mapEventBus.emitLongPress({ lat: 5, lng: 6 });
    expect(cb1).toHaveBeenCalledTimes(1);
    expect(cb2).toHaveBeenCalledTimes(1);
    mapEventBus.unsubscribeLongPress(cb1);
    mapEventBus.unsubscribeLongPress(cb2);
  });
});
