import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { GlobalSearch } from "@/components/chat/GlobalSearch";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-[calc(100vh-56px)]">
      <ChatSidebar />
      <div className="flex-1 min-w-0">{children}</div>
      <GlobalSearch />
    </div>
  );
}
