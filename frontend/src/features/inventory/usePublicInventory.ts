import { useQuery } from "@tanstack/react-query";

import {
  fetchPublicInventory,
  fetchPublicMakerspaces,
  publicInventoryKey,
  publicMakerspacesKey,
} from "./api";

export function usePublicMakerspaces() {
  return useQuery({
    queryKey: publicMakerspacesKey,
    queryFn: fetchPublicMakerspaces,
  });
}

export function usePublicInventory(slug: string, page: number, query: string) {
  return useQuery({
    queryKey: publicInventoryKey(slug, page, query),
    queryFn: () => fetchPublicInventory(slug, page, query),
    placeholderData: (previousData) => previousData,
  });
}
