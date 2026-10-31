import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// Screen recording prevention (best-effort - not foolproof, but adds friction)
document.addEventListener('keydown', (e) => {
  // Block common screenshot shortcuts on Windows/Linux
  if (e.key === 'PrintScreen') {
    e.preventDefault()
  }
})

// Prevent right-click on content areas
document.addEventListener('contextmenu', (e) => {
  if (e.target.closest('.protected-content')) {
    e.preventDefault()
  }
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
