import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import './workroom.css'
import './quiet-cinema.css'
import './ui-polish.css'
import './bot-polish.css'
import App from './App'
// Last on purpose: the pages import their own sheets, and this one sets the current surface over them.
import './obsidian.css'
// Paper surface (2026-09-29 redesign): sidebar shell, warm palette, round pastel bot faces, chat bubbles.
import './paper.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
