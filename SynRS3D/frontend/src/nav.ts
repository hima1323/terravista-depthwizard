import { Home, Layers, Box, Target, ShieldAlert, Waves, Tent, ClipboardCheck, type LucideIcon } from 'lucide-react';
import type { Page } from './engine/Engine';

export interface PageMeta { page: Page; path: string; label: string; phase: string; group: 'workspace' | 'cycle'; icon: LucideIcon; c: string; rgb: string; title: string; blurb: string }

// Accent colours match the [data-page] tokens in styles.css
export const PAGES: PageMeta[] = [
  { page: 'home', path: '/', label: 'Home', phase: 'Start', group: 'workspace', icon: Home, c: '#e9eef2', rgb: '233,238,242',
    title: 'DepthWizard', blurb: 'What DepthWizard does and how accurate it is.' },
  { page: 'scenes', path: '/scenes', label: 'Scenes', phase: 'Library', group: 'workspace', icon: Layers, c: '#e8889a', rgb: '232,136,154',
    title: 'Scene library', blurb: 'Choose a processed scene or upload a new image.' },
  { page: 'explore', path: '/explore', label: 'Explore', phase: 'Height model', group: 'workspace', icon: Box, c: '#9ab8d3', rgb: '154,184,211',
    title: 'Explore heights', blurb: 'Fly through the reconstructed scene, measure any point, export GeoTIFF / 3D.' },
  { page: 'validate', path: '/validate', label: 'Validate', phase: 'Accuracy', group: 'workspace', icon: Target, c: '#aea6dc', rgb: '174,166,220',
    title: 'Validate & calibrate', blurb: 'Check heights against LiDAR, survey points or NASA ICESat-2, and calibrate with control points.' },
  { page: 'prepare', path: '/prepare', label: 'Prepare', phase: 'Before', group: 'cycle', icon: ShieldAlert, c: '#d3bd72', rgb: '211,189,114',
    title: 'Hazard & exposure', blurb: 'Landslide-prone slopes and how many buildings each water rise would reach, before anything happens.' },
  { page: 'respond', path: '/respond', label: 'Respond', phase: 'During', group: 'cycle', icon: Waves, c: '#64a6dd', rgb: '100,166,221',
    title: 'Flood response', blurb: 'Run a flood scenario, step through rain and river rise hour by hour, and find routes that stay dry.' },
  { page: 'relief', path: '/relief', label: 'Relief', phase: 'Shelter', group: 'cycle', icon: Tent, c: '#8fd1c4', rgb: '143,209,196',
    title: 'Relief sites', blurb: 'Flat, open, dry places for helicopters and relief camps, with capacity and road access.' },
  { page: 'assess', path: '/assess', label: 'Assess', phase: 'After', group: 'cycle', icon: ClipboardCheck, c: '#e58a6c', rgb: '229,138,108',
    title: 'Impact report', blurb: 'What the current scenario affects, block by block, ready to export.' },
];
export const metaOf = (p: Page) => PAGES.find(x => x.page === p)!;
export const pageOfPath = (path: string): Page => (PAGES.find(x => x.path === path) || PAGES[0]).page;
