import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { type Makerspace, useStaffGet } from "./panels/shared";

type Props = {
  makerspace: Makerspace;
};

function fieldValue(value?: string | null) {
  return value ?? "";
}

export function LocationSettings({ makerspace }: Props) {
  const queryClient = useQueryClient();
  const settings = useStaffGet<Makerspace>(
    ["makerspace-settings", makerspace.id],
    `/admin/makerspaces/${makerspace.id}`,
  );
  const source = settings.data ?? makerspace;
  const [location, setLocation] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [geoError, setGeoError] = useState("");
  const coordinateError =
    Boolean(latitude.trim()) !== Boolean(longitude.trim())
      ? "Latitude and longitude must be set together."
      : "";

  useEffect(() => {
    setLocation(fieldValue(source.location));
    setLatitude(fieldValue(source.latitude));
    setLongitude(fieldValue(source.longitude));
    setGeoError("");
  }, [makerspace.id, source.location, source.latitude, source.longitude]);

  const saveLocation = useMutation({
    mutationFn: () =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          location: location.trim(),
          latitude: latitude.trim() || null,
          longitude: longitude.trim() || null,
        }),
      }),
    onSuccess: (updated) => {
      setLocation(fieldValue(updated.location));
      setLatitude(fieldValue(updated.latitude));
      setLongitude(fieldValue(updated.longitude));
      queryClient.setQueryData(["makerspace-settings", makerspace.id], updated);
      queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
      queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    },
  });

  function useCurrentLocation() {
    setGeoError("");
    if (!navigator.geolocation) {
      setGeoError("Geolocation is not supported in this browser.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatitude(position.coords.latitude.toFixed(6));
        setLongitude(position.coords.longitude.toFixed(6));
      },
      () => {
        setGeoError(
          "Could not access your current location. Allow location permission and use HTTPS or localhost.",
        );
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  const previewUrl = settings.data?.map_url ?? makerspace.map_url ?? "";
  const saveDisabled = settings.isLoading || saveLocation.isPending || Boolean(coordinateError);

  return (
    <div className="rounded-2xl border border-ink bg-bg p-4 shadow-brutal-sm">
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (!saveDisabled) {
            saveLocation.mutate();
          }
        }}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="grid max-w-2xl gap-2">
            <h3 className="text-base font-semibold text-ink">Location & map</h3>
            <p className="text-sm text-muted">
              Public location label and coordinates used to generate the Google Maps link.
            </p>
          </div>
          <button className="desk-button-primary" disabled={saveDisabled} type="submit">
            {saveLocation.isPending ? "Saving..." : "Save location"}
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-sm font-semibold text-ink sm:col-span-2">
            <span>Location</span>
            <input
              className="desk-input"
              placeholder="Workshop address or public location label"
              value={location}
              onChange={(event) => setLocation(event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm font-semibold text-ink">
            <span>Latitude</span>
            <input
              className="desk-input"
              inputMode="decimal"
              placeholder="12.971599"
              value={latitude}
              onChange={(event) => setLatitude(event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm font-semibold text-ink">
            <span>Longitude</span>
            <input
              className="desk-input"
              inputMode="decimal"
              placeholder="77.594566"
              value={longitude}
              onChange={(event) => setLongitude(event.target.value)}
            />
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button className="desk-button" type="button" onClick={useCurrentLocation}>
            Use my current location
          </button>
          {previewUrl ? (
            <a
              className="font-mono text-xs font-semibold uppercase text-secondary underline-offset-2 hover:underline"
              href={previewUrl}
              rel="noopener noreferrer"
              target="_blank"
            >
              Preview on Google Maps
            </a>
          ) : null}
        </div>

        {coordinateError ? <p className="text-sm text-danger">{coordinateError}</p> : null}
        {geoError ? <p className="text-sm text-danger">{geoError}</p> : null}
        {saveLocation.error ? (
          <p className="text-sm text-danger">{saveLocation.error.message}</p>
        ) : null}
      </form>
    </div>
  );
}
