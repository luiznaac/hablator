import { ChannelsPanel } from "./console/ChannelsPanel.tsx";
import { HealthPanel } from "./console/HealthPanel.tsx";
import { HistoryPanel } from "./console/HistoryPanel.tsx";
import { SendPanel } from "./console/SendPanel.tsx";

// The debug console: send left, history centre, health + channels right; stacks below `lg`.
export function Console() {
  return (
    <div className="grid grid-cols-12 gap-3">
      <div className="col-span-12 lg:col-span-3">
        <SendPanel />
      </div>
      <div className="col-span-12 lg:col-span-5">
        <HistoryPanel />
      </div>
      <div className="col-span-12 space-y-3 lg:col-span-4">
        <HealthPanel />
        <ChannelsPanel />
      </div>
    </div>
  );
}
