UI refresh (D&D theme)

Overview
- Modernized the chat UI with a subtle D&D-inspired theme.
- Introduced a left sidebar for future tools, a main chat area, and a sticky footer composer.
- Kept all existing behavior and API usage (no backend changes).

Structure
- src/components/Sidebar.jsx: Vertical nav with placeholder tools (disabled for now).
- src/components/ChatWindow.jsx: Scrollable list of messages with auto-scroll to latest.
- src/components/Message.jsx: Parchment-style message bubbles for Me vs DM.
- src/components/Composer.jsx: Sticky footer textarea and Send button; Enter or Cmd/Ctrl+Enter sends.
- src/theme.css: Theme variables and base typography.
- src/App.css: Layout and component styles using the theme variables.
- public/index.html: Loads Google Fonts (Cinzel for headings, Spectral for body).

Theme tokens (src/theme.css)
- --bg-base: #0e1012 (near-black)
- --panel: #1b2420 (deep forest)
- --parchment: #f3ead7 (paper)
- --ink: #1b1b1b (text)
- --muted-ink: #c7c1b5
- --accent: #c9a227 (antique gold)
- --accent-2: #6b2e2e (burgundy)
- --ring: 0 0 0 2px var(--accent) inset
- --radius: 12px

Tweaking colors/fonts
- Edit src/theme.css to adjust colors, radius, and focus ring.
- Update Google Fonts in public/index.html if you want different typefaces.
- Component styles are in src/App.css; prefer using the variables over hardcoded colors.

Accessibility
- Semantic regions: <nav>, <main>, <footer>.
- Visible focus rings (via --ring) for buttons and textarea.
- Buttons include aria-labels.

Responsive behavior
- Desktop: Two-column layout (sidebar 280px + chat).
- < 768px: Sidebar hides; chat and composer use full width.

Dev
- Install and run from frontend/chatbot-frontend:
  - npm install
  - npm start
- App should start without console errors.
