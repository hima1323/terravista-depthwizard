import { useEffect } from 'react';
import { Route, Routes, useLocation } from 'react-router-dom';
import { engine, useEngine } from './engine/useEngine';
import { pageOfPath } from './nav';
import Stage from './components/Stage';
import Rail from './components/Rail';
import TopBar from './components/TopBar';
import Toolbar from './components/Toolbar';
import Home from './pages/Home';
import Scenes from './pages/Scenes';
import Explore from './pages/Explore';
import Validate from './pages/Validate';
import Prepare from './pages/Prepare';
import Respond from './pages/Respond';
import Relief from './pages/Relief';
import Assess from './pages/Assess';

function Hint() {
  const hint = useEngine(s => s.hint);
  return hint ? <div className="toast glass" role="status" key={hint}>{hint}</div> : null;
}

export default function App() {
  const loc = useLocation(), page = useEngine(s => s.page);
  useEffect(() => { engine.setPage(pageOfPath(loc.pathname)); }, [loc.pathname]);
  return (
    <div className="app" data-page={page}>
      <Stage />
      <Rail />
      <TopBar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/scenes" element={<Scenes />} />
        <Route path="/explore" element={<Explore />} />
        <Route path="/validate" element={<Validate />} />
        <Route path="/prepare" element={<Prepare />} />
        <Route path="/respond" element={<Respond />} />
        <Route path="/relief" element={<Relief />} />
        <Route path="/assess" element={<Assess />} />
        <Route path="*" element={<Home />} />
      </Routes>
      <Toolbar />
      <Hint />
    </div>
  );
}
