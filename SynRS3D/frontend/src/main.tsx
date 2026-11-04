import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import '@fontsource-variable/manrope';
import '@fontsource-variable/caveat';
import './styles.css';
import App from './App';

// Hash routing: app.py serves one static index.html, and deep links (#/respond) still work offline.
createRoot(document.getElementById('root')!).render(
  <StrictMode><HashRouter><App /></HashRouter></StrictMode>,
);
