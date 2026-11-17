import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type HistoryFilters, buildHistoryQuery } from "../lib/history.ts";
import { api } from "./client.ts";
import type { Channel, ChannelConfigRequestDTO, NotificationRequestDTO } from "./types.ts";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.getHealth,
    // The panel shows a last-checked time, so a focus must re-check rather than trust a cache.
    staleTime: 0,
    refetchOnWindowFocus: true,
  });
}

export function useNotifications(filters: HistoryFilters, offset: number) {
  return useQuery({
    queryKey: ["notifications", filters, offset],
    queryFn: () => api.listNotifications(buildHistoryQuery(filters, offset)),
    // The console refreshes on load, on window focus and on the manual button — never by polling.
    // `staleTime: 0` keeps the focus refetch from being suppressed by the global 30 s cache.
    staleTime: 0,
    refetchOnWindowFocus: true,
  });
}

export function useNotification(id: number) {
  return useQuery({
    queryKey: ["notification", id],
    queryFn: () => api.getNotification(id),
  });
}

export function useChannels() {
  return useQuery({
    queryKey: ["channels"],
    queryFn: api.getChannels,
    refetchOnWindowFocus: true,
  });
}

export function useSendNotification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: NotificationRequestDTO) => api.createNotification(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

export function useRetryDelivery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.retryDelivery(id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
        queryClient.invalidateQueries({ queryKey: ["notification"] }),
      ]);
    },
  });
}

export function useSaveChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { channel: Channel; body: ChannelConfigRequestDTO }) =>
      api.putChannel(input.channel, input.body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["channels"] }),
  });
}

export function useDisableChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (channel: Channel) => api.deleteChannel(channel),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["channels"] }),
  });
}
