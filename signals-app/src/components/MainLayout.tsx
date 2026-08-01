/**
 * Main app shell: scrollable screen area + persistent compliance footer +
 * bottom tab bar. The compliance footer sits ABOVE the tab bar on every main
 * view, satisfying the "visible on every Signals view" requirement.
 */
import { Outlet } from 'react-router-dom';
import ComplianceFooter from './ComplianceFooter';
import TabBar from './TabBar';

export default function MainLayout() {
  return (
    <div className="flex h-full flex-col">
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
      <ComplianceFooter />
      <TabBar />
    </div>
  );
}
