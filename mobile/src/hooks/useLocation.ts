import { useEffect } from "react";
import * as Location from "expo-location";

import { useAppStore } from "../store/useAppStore";

export function useLocation() {
  const location = useAppStore((s) => s.location);
  const setLocation = useAppStore((s) => s.setLocation);

  useEffect(() => {
    if (location) return;
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") return;
      try {
        const pos = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.Balanced,
        });
        setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      } catch {
        /* ignore — user can still use app without location */
      }
    })();
  }, [location, setLocation]);

  return location;
}
