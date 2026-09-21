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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
